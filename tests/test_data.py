import copy
import json

import httpx
import pandas as pd
import pytest

from gridflex.config import Settings
from gridflex.data import (
    DataQualityError,
    Sources,
    SourceUnavailable,
    parse_carbon,
    parse_weather,
    quality_report,
    save_silver,
    snapshot,
)


def test_nullable_actuals_are_preserved(carbon_payload):
    f = parse_carbon(carbon_payload)
    assert len(f) == 2 and pd.isna(f.actual.iloc[1]) and f.forecast.iloc[1] == 105


@pytest.mark.parametrize("fault", ["negative", "duplicate", "duration", "missing", "naive", "infinity"])
def test_schema_rejects_corruption(carbon_payload, fault):
    p = copy.deepcopy(carbon_payload)
    if fault == "negative":
        p["data"][0]["intensity"]["actual"] = -999
    if fault == "duplicate":
        p["data"].append(p["data"][0])
    if fault == "duration":
        p["data"][0]["to"] = "2026-01-01T01:00Z"
    if fault == "missing":
        del p["data"][0]["intensity"]["forecast"]
    if fault == "naive":
        p["data"][0]["from"] = "2026-01-01T00:00"
    if fault == "infinity":
        p["data"][0]["intensity"]["actual"] = float("inf")
    with pytest.raises(DataQualityError):
        parse_carbon(p)


def test_snapshots_immutable_and_content_addressed(tmp_path, carbon_payload):
    key = snapshot(tmp_path, "neso", carbon_payload, {"url": "https://example.test"})
    path = tmp_path / "raw" / "neso" / f"{key}.json"
    original = path.read_bytes()
    assert snapshot(tmp_path, "neso", carbon_payload, {}) == key
    assert path.read_bytes() == original
    assert json.loads(original)["payload"] == carbon_payload


def test_storage_upserts_revised_actuals_and_keeps_known_values(tmp_path, carbon_payload):
    f = parse_carbon(carbon_payload)
    save_silver(f, tmp_path)
    f.loc[0, "actual"] = 90  # A downward source revision must replace 110.
    f.loc[1, "actual"] = 100
    save_silver(f, tmp_path)
    f.loc[1, "actual"] = float("nan")
    save_silver(f, tmp_path)
    stored = pd.read_csv(tmp_path / "processed" / "carbon.csv")
    assert stored.actual.tolist() == [90, 100] and len(stored) == 2


def test_missing_intervals_are_reported(carbon):
    r = quality_report(carbon.drop(index=7))
    assert r["missing_intervals"] == 1 and r["coverage"] < 1


def test_carbon_refresh_preserves_weather_history(tmp_path, carbon_payload):
    frame = parse_carbon(carbon_payload)
    frame["temperature_2m"] = [10.0, 11.0]
    save_silver(frame, tmp_path)
    save_silver(frame.drop(columns="temperature_2m"), tmp_path)
    context = pd.read_csv(tmp_path / "processed" / "context.csv")
    assert context.temperature_2m.tolist() == [10.0, 11.0]


def test_http_adapter_filters_inclusive_api_boundary(carbon_payload, tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=carbon_payload)))
    s = Sources(Settings(data_dir=tmp_path), client)
    result = s.carbon("2026-01-01T00:30Z", "2026-01-01T01:00Z")
    assert len(result) == 1 and result.timestamp.iloc[0].minute == 30
    s.close()


def test_http_permanent_failure_does_not_retry(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404)

    s = Sources(Settings(data_dir=tmp_path), httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(SourceUnavailable):
        s.get("https://example.test")
    assert len(calls) == 1
    s.close()


def test_weather_units_and_nulls():
    p = {
        "utc_offset_seconds": 0,
        "hourly_units": {
            "temperature_2m": "°C",
            "wind_speed_10m": "km/h",
            "cloud_cover": "%",
            "shortwave_radiation": "W/m²",
        },
        "hourly": {
            "time": ["2026-01-01T00:00"],
            "temperature_2m": [10],
            "wind_speed_10m": [20],
            "cloud_cover": [90],
            "shortwave_radiation": [0],
        },
    }
    assert parse_weather(p, "London").location.iloc[0] == "London"
    p["hourly_units"]["wind_speed_10m"] = "m/s"
    with pytest.raises(DataQualityError):
        parse_weather(p, "London")
