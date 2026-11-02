"""Regression tests for recurring failed-run emails caused by advisory model alerts."""

import copy
import json
from types import SimpleNamespace

import pytest

from gridflex import cli
from gridflex.config import Settings
from gridflex.data import DataQualityError, SourceUnavailable
from gridflex.monitoring import maintenance_exit_code


@pytest.fixture
def alert_report():
    # Synthetic report matching the observed failure mode, not a measured result.
    return {
        "status": "alert",
        "data_freshness": {"status": "ok"},
        "forecast_issuance": {"status": "ok", "error": None},
        "weather_ingestion": {"status": "ok", "error_type": None},
        "drift": {"status": "alert", "threshold": 0.25, "features": {"mean_24h": 0.62}},
        "performance": {
            "status": "alert",
            "coverage": 0.873,
            "coverage_alert_threshold": 0.9,
            "mae": 30.2,
            "distinct_origins": 29,
            "target_days": 8,
        },
    }


def test_model_warning_is_advisory_only_when_requested(alert_report):
    before = copy.deepcopy(alert_report)
    assert maintenance_exit_code(alert_report) == 2
    assert maintenance_exit_code(alert_report, advisory_model_alerts=True) == 0
    assert alert_report == before  # No metric, threshold or monitoring status rewritten.


@pytest.mark.parametrize("signal", ["data_freshness", "forecast_issuance", "weather_ingestion"])
def test_operational_alerts_still_fail_in_advisory_mode(alert_report, signal):
    alert_report[signal]["status"] = "degraded"
    assert maintenance_exit_code(alert_report, advisory_model_alerts=True) == 2


@pytest.mark.parametrize("state", ["ok", "insufficient_data"])
def test_valid_collection_without_model_alerts_succeeds(alert_report, state):
    alert_report["status"] = state
    alert_report["drift"]["status"] = state
    alert_report["performance"]["status"] = state
    assert maintenance_exit_code(alert_report) == 0
    assert maintenance_exit_code(alert_report, advisory_model_alerts=True) == 0


@pytest.mark.parametrize("signal", ["status", "drift", "performance"])
def test_unknown_report_status_is_not_suppressed(alert_report, signal):
    if signal == "status":
        alert_report[signal] = "unexpected"
    else:
        alert_report[signal]["status"] = "unexpected"
    assert maintenance_exit_code(alert_report, advisory_model_alerts=True) == 2


def test_unexplained_aggregate_alert_is_not_suppressed(alert_report):
    alert_report["drift"]["status"] = "ok"
    alert_report["performance"]["status"] = "ok"
    assert maintenance_exit_code(alert_report, advisory_model_alerts=True) == 2


@pytest.mark.parametrize("failure", [None, "weather", "forecast", "freshness", "carbon"])
def test_cli_keeps_model_warnings_visible_and_real_failures_fatal(
    alert_report, carbon, tmp_path, monkeypatch, capsys, failure
):
    def get_carbon(*args):
        if failure == "carbon":
            raise SourceUnavailable("synthetic source outage")
        return carbon

    def get_weather():
        if failure == "weather":
            raise SourceUnavailable("synthetic weather outage")
        return None

    def issue_forecast(mode):
        if failure == "forecast":
            raise DataQualityError("synthetic missing recent actuals")
        return {"status": "issued"}

    if failure == "freshness":
        alert_report["data_freshness"]["status"] = "alert"
    source = SimpleNamespace(carbon=get_carbon, weather=get_weather, close=lambda: None)
    service = SimpleNamespace(forecast=issue_forecast, sources=source)
    monkeypatch.setattr(cli, "Settings", lambda: Settings(data_dir=tmp_path))
    monkeypatch.setattr(cli, "Sources", lambda settings: source)
    monkeypatch.setattr(cli, "ForecastService", lambda settings: service)
    monkeypatch.setattr(cli, "monitor", lambda settings: copy.deepcopy(alert_report))
    monkeypatch.setattr("sys.argv", ["gridflex", "maintenance", "--advisory-model-alerts"])
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    if failure == "carbon":
        with pytest.raises(SourceUnavailable):
            cli.main()
        assert not (tmp_path / "processed/monitoring.json").exists()
        return
    if failure:
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 2
    else:
        cli.main()
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report == json.loads((tmp_path / "processed/monitoring.json").read_text())
    assert report["status"] == "alert"
    assert report["performance"] == alert_report["performance"]
    assert report["drift"] == alert_report["drift"]
    assert "87.3%" in summary.read_text() and "90.0%" in summary.read_text()
    if failure:
        assert report["execution_status"] == "failed"
    else:
        assert report["execution_status"] == "completed_with_model_alerts"
        assert "::warning title=Model monitoring requires review::" in captured.err
