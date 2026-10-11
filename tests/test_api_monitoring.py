from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from gridflex.api import create_app
from gridflex.config import Settings
from gridflex.data import SourceUnavailable
from gridflex.monitoring import drift_report, performance_report, reference_profile
from gridflex.service import ForecastService


def test_api_replay_schedule_csv_and_metrics(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path, model_dir=Path("models/production")))) as c:
        assert c.get("/health").json()["status"] == "ok"
        assert c.get("/ready").status_code == 200
        r = c.get("/api/v1/forecast")
        assert r.json()["mode"] == "replay" and len(r.json()["slots"]) == 48
        assert "nosniff" == r.headers["x-content-type-options"]
        result = c.post("/api/v1/schedule", json={}).json()
        assert result["slots"][-1]["soc"] == 0.8
        assert c.post("/api/v1/schedule", json={"available_slots": 1}).status_code == 422
        assert c.get("/api/v1/forecast?mode=invalid").status_code == 422
        assert "prediction" in c.get("/api/v1/forecast.csv").text
        assert "gridflex_requests_total" in c.get("/metrics").text
        assert "GridFlex" in c.get("/").text
        assert c.get("/static/app.js").status_code == 200
        assert c.get("/api/v1/monitoring").json()["status"] == "not_yet_scored"


def test_live_failure_never_masquerades_as_replay(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, model_dir=Path("models/production"))
    service = ForecastService(settings)

    def failed(*args, **kwargs):
        raise SourceUnavailable("offline")

    monkeypatch.setattr(service.sources, "carbon", failed)
    with TestClient(create_app(settings, service)) as c:
        assert c.get("/api/v1/forecast?mode=live").status_code == 503
        assert c.get("/api/v1/forecast").json()["mode"] == "replay"
    service.sources.close()


def test_drift_and_delayed_performance():
    ref = pd.DataFrame({"x": np.arange(1000)})
    spec = reference_profile(ref, ["x"])
    assert drift_report(ref, spec)["status"] == "ok"
    assert drift_report(pd.DataFrame({"x": np.arange(1000) + 2000}), spec)["status"] == "alert"
    assert drift_report(ref.head(), spec)["status"] == "insufficient_data"
    t = pd.date_range("2026-01-01", periods=60, freq="30min", tz="UTC")
    forecasts = pd.DataFrame(
        {"origin": t.floor("6h"), "timestamp": t, "prediction": 100, "lower": 80, "upper": 120}
    )
    actuals = pd.DataFrame({"timestamp": t, "actual": 105})
    assert performance_report(forecasts, actuals, 10)["mae"] == 5
    actuals.actual = 150
    assert performance_report(forecasts, actuals, 10)["status"] == "insufficient_data"
    assert performance_report(forecasts, actuals, 10, min_origins=1, min_days=1)["status"] == "alert"
