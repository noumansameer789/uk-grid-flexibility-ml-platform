"""Regression checks for audit findings, using synthetic fixtures unless labelled real."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gridflex.api import create_app
from gridflex.cli import read_carbon
from gridflex.config import Settings
from gridflex.data import DataQualityError, Sources, SourceUnavailable
from gridflex.evaluation import charging_evaluation, seasonal_baselines
from gridflex.features import series_from_frame
from gridflex.model import conformal_radius, load_bundle
from gridflex.monitoring import performance_report
from gridflex.service import ForecastService
from gridflex.storage import StorageUnavailable, first_json, read_json


def test_maintenance_still_scores_when_new_forecast_cannot_issue(carbon, tmp_path, monkeypatch, capsys):
    from gridflex import cli

    def no_forecast(mode):
        raise DataQualityError("Delayed upstream actuals")

    source = SimpleNamespace(carbon=lambda *args: carbon, weather=lambda: None, close=lambda: None)
    service = SimpleNamespace(forecast=no_forecast, sources=source)
    monkeypatch.setattr(cli, "Settings", lambda: Settings(data_dir=tmp_path))
    monkeypatch.setattr(cli, "Sources", lambda settings: source)
    monkeypatch.setattr(cli, "ForecastService", lambda settings: service)
    monkeypatch.setattr("sys.argv", ["gridflex", "maintenance"])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["forecast_issuance"]["status"] == "degraded"
    assert report["performance"]["status"] == "insufficient_data"
    assert read_json(tmp_path / "processed/monitoring.json")["status"] == "alert"


def test_first_writer_is_canonical_and_atomic(tmp_path):
    path = tmp_path / "issued.json"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: first_json(path, {"writer": i}), range(16)))
    assert all(result == read_json(path) for result in results)
    assert not list(tmp_path.glob("*.lock"))
    path.write_text("{broken")
    with pytest.raises(StorageUnavailable):
        first_json(path, {"writer": "must not overwrite corrupt evidence"})


def test_live_forecast_survives_restart_without_reissuing(carbon, tmp_path):
    calls = []
    settings = Settings(data_dir=tmp_path)

    def clock():
        return pd.Timestamp("2025-04-01T23:55Z")

    def fetch(*args):
        calls.append(args)
        return carbon.copy()

    original = ForecastService(settings, SimpleNamespace(carbon=fetch), clock).forecast("live")
    restarted = ForecastService(settings, SimpleNamespace(carbon=fetch), clock).forecast("live")
    assert original == restarted and len(calls) == 1
    assert original["issued_at"] < original["origin"]
    assert len(original["forecast_id"]) == 64
    saved = next((tmp_path / "issued").glob("*.json"))
    corrupted = json.loads(saved.read_text())
    corrupted["slots"][0]["prediction"] += 1
    saved.write_text(json.dumps(corrupted))
    with pytest.raises(DataQualityError, match="integrity"):
        ForecastService(settings, SimpleNamespace(carbon=fetch), clock).forecast("live")


def test_source_failure_cooldown(tmp_path):
    calls = []

    def fail(*args):
        calls.append(1)
        raise SourceUnavailable("offline")

    service = ForecastService(Settings(data_dir=tmp_path), SimpleNamespace(carbon=fail))
    for _ in range(3):
        with pytest.raises(SourceUnavailable):
            service.forecast("live")
    assert len(calls) == 1


def test_weather_requires_current_complete_context(tmp_path):
    source = SimpleNamespace(
        weather=lambda **kw: pd.DataFrame(
            {"timestamp": [pd.Timestamp("2025-01-01T00:00Z")], "location": ["London"]}
        )
    )
    service = ForecastService(Settings(data_dir=tmp_path), source)
    with pytest.raises(DataQualityError):
        service.weather()
    with pytest.raises(SourceUnavailable, match="cooldown"):
        service.weather()


def test_partial_carbon_response_fails_closed(carbon_payload, tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=carbon_payload)))
    source = Sources(Settings(data_dir=tmp_path), client)
    with pytest.raises(DataQualityError):
        source.carbon("2026-01-01T00:00Z", "2026-01-01T02:00Z")
    with pytest.raises(ValueError):
        source.carbon("2026-01-01T00:01Z", "2026-01-01T01:00Z")
    source.close()


def test_api_limits_and_forecast_binding(tmp_path):
    settings = Settings(data_dir=tmp_path, max_body_bytes=512, api_requests_per_minute=8)
    with TestClient(create_app(settings)) as client:
        forecast = client.get("/api/v1/forecast").json()
        response = client.post("/api/v1/schedule", json={"expected_forecast_id": forecast["forecast_id"]})
        assert response.status_code == 200
        assert response.json()["forecast_id"] == forecast["forecast_id"]
        assert client.post("/api/v1/schedule", json={"expected_forecast_id": "0" * 64}).status_code == 409
        assert client.get("/api/v1/forecast.csv?expected_forecast_id=" + "0" * 64).status_code == 409
        assert client.post("/api/v1/schedule", content=b"x" * 513).status_code == 413
        for _ in range(3):
            assert client.get("/api/v1/model").status_code == 200
        assert client.get("/api/v1/model").status_code == 429
        assert client.get("/health").status_code == 200


def test_monitoring_stale_and_invalid_reports(tmp_path):
    folder = tmp_path / "processed"
    folder.mkdir()
    path = folder / "monitoring.json"
    path.write_text(json.dumps({"status": "ok", "generated_at": "2025-01-01T00:00:00Z"}))
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        assert client.get("/api/v1/monitoring").json()["status"] == "stale"
        path.write_text(json.dumps({"status": "ok", "generated_at": "2025-01-01"}))
        assert client.get("/api/v1/monitoring").status_code == 503


def test_csv_rejects_naive_timestamps_and_out_of_range_actuals(carbon, tmp_path):
    bad = carbon.head().copy()
    bad["timestamp"] = bad.timestamp.dt.tz_localize(None)
    path = tmp_path / "bad.csv"
    bad.to_csv(path, index=False)
    with pytest.raises(DataQualityError):
        read_carbon(path)
    bad = carbon.head().copy()
    bad.loc[0, "actual"] = -999
    with pytest.raises(DataQualityError):
        series_from_frame(bad)


def test_added_baselines_obey_observation_delay(carbon):
    origin = pd.Timestamp("2025-04-01T00:00Z")
    timestamps = pd.date_range(origin, periods=48, freq="30min")
    frame = pd.DataFrame({"origin": origin, "timestamp": timestamps})
    expected = seasonal_baselines(carbon, frame)
    changed = carbon.copy()
    changed.loc[changed.timestamp >= origin - pd.Timedelta(hours=2), "actual"] = 999
    pd.testing.assert_frame_equal(expected, seasonal_baselines(changed, frame))


def test_monitoring_refuses_duplicated_evidence():
    t = pd.Timestamp("2025-04-01T00:00Z")
    forecasts = pd.DataFrame({"origin": [t, t], "timestamp": [t, t]})
    with pytest.raises(ValueError, match="Duplicate"):
        performance_report(forecasts, pd.DataFrame(), 10)


def test_real_candidate_fails_strict_gate():
    card = load_bundle(Path("models/production"))["card"]
    assert card["summary"]["seven_day_mean"]["mae"] < card["summary"]["lightgbm"]["mae"]
    assert card["summary"]["lightgbm"]["coverage"] < card["nominal_coverage"]
    assert card["candidate_gate_passed"] is False
    with pytest.raises(ValueError):
        conformal_radius([-1, 2])


def test_charging_evaluation_scores_actuals_not_predictions():
    origin = pd.Timestamp("2025-01-01T00:00Z")
    frame = pd.DataFrame(
        {
            "origin": origin,
            "timestamp": pd.date_range(origin, periods=48, freq="30min"),
            "prediction": list(range(48)),
            "target": list(range(48, 0, -1)),
        }
    )
    result = charging_evaluation(frame).iloc[0]
    assert result.observed_schedule_proxy_kg > result.forecast_weighted_kg
    assert result.regret_vs_perfect_information_kg > 0
