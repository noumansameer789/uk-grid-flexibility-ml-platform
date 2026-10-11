import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

from gridflex.config import Settings
from gridflex.data import DataQualityError, SourceUnavailable
from gridflex.limits import RequestLimits
from gridflex.optimise import ChargingRequest, optimise
from gridflex.service import ForecastService
from gridflex.storage import StorageUnavailable, read_json


class JsonFormatter(logging.Formatter):
    def format(self, record):
        event = record.msg if isinstance(record.msg, dict) else {"event": record.getMessage()}
        return json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                **event,
                "error_type": getattr(record, "error_type", None),
            }
        )


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
log = logging.getLogger("gridflex")
log.handlers = [handler]
log.setLevel(os.getenv("GRIDFLEX_LOG_LEVEL", "INFO"))


def create_app(settings: Settings | None = None, service=None):
    settings = settings or Settings()
    registry = CollectorRegistry()
    requests = Counter("gridflex_requests_total", "HTTP requests", ["route", "status"], registry=registry)
    latency = Histogram("gridflex_request_seconds", "HTTP response time", ["route"], registry=registry)

    @asynccontextmanager
    async def lifespan(app):
        app.state.service = service or ForecastService(settings)
        yield
        if service is None:
            app.state.service.sources.close()

    app = FastAPI(
        title="GridFlex GB",
        version="1.0.0",
        lifespan=lifespan,
        description="GB carbon forecasts and constrained charging schedules. Research use; no charger control.",
    )
    app.add_middleware(
        RequestLimits,
        max_body_bytes=settings.max_body_bytes,
        requests_per_minute=settings.api_requests_per_minute,
    )

    @app.middleware("http")
    async def observe(request: Request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        # Use route templates to prevent unbounded metric label cardinality.
        route = getattr(request.scope.get("route"), "path", "unmatched")
        requests.labels(route, response.status_code).inc()
        latency.labels(route).observe(time.monotonic() - started)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        if request.url.path in ("/docs", "/redoc", "/docs/oauth2-redirect"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
            )
        log.info(
            {
                "event": "http_request",
                "route": route,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            }
        )
        return response

    def fetch(request: Request, mode: str):
        try:
            return request.app.state.service.forecast(mode)
        except (SourceUnavailable, DataQualityError, StorageUnavailable) as exc:
            raise HTTPException(
                503, "Live data is unavailable or incomplete. Historical replay remains available."
            ) from exc

    @app.get("/health", tags=["operations"])
    def health():
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/ready", tags=["operations"])
    def ready(request: Request):
        return {"status": "ready", "model_sha256": request.app.state.service.bundle["card"]["model_sha256"]}

    @app.get("/api/v1/forecast", tags=["forecast"])
    def forecast(request: Request, mode: Literal["replay", "live"] = "replay"):
        return fetch(request, mode)

    @app.post("/api/v1/schedule", tags=["charging"])
    def schedule(body: ChargingRequest, request: Request):
        result = fetch(request, body.mode)
        if body.expected_forecast_id is not None and body.expected_forecast_id != result["forecast_id"]:
            raise HTTPException(409, "Forecast changed. Refresh the chart before calculating a plan.")
        try:
            response = optimise(pd.DataFrame(result["slots"]), body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            **response,
            "forecast_mode": result["mode"],
            "forecast_origin": result["origin"],
            "forecast_id": result["forecast_id"],
            "notice": result["notice"],
        }

    @app.get("/api/v1/model", tags=["evidence"])
    def model(request: Request):
        return request.app.state.service.bundle["card"]

    @app.get("/api/v1/weather", tags=["context"])
    def weather(request: Request):
        try:
            return request.app.state.service.weather()
        except (SourceUnavailable, DataQualityError, StorageUnavailable) as exc:
            raise HTTPException(503, "Weather context is currently unavailable") from exc

    @app.get("/api/v1/monitoring", tags=["operations"])
    def monitoring():
        path = settings.data_dir / "processed" / "monitoring.json"
        if path.exists():
            try:
                report = read_json(path)
                age = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(report["generated_at"])).total_seconds()
                return {
                    **report,
                    "stale": age > 8 * 3600,
                    "age_seconds": max(0, round(age)),
                    "status": "stale" if age > 8 * 3600 else report["status"],
                }
            except (StorageUnavailable, KeyError, ValueError, TypeError) as exc:
                raise HTTPException(503, "Monitoring report is unavailable or invalid") from exc
        return {
            "status": "not_yet_scored",
            "note": "Run gridflex monitor after issued forecasts receive actual labels.",
        }

    @app.get("/metrics", tags=["operations"])
    def prometheus():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/api/v1/forecast.csv", tags=["forecast"])
    def csv_export(
        request: Request,
        mode: Literal["replay", "live"] = Query("replay"),
        expected_forecast_id: str | None = Query(None, pattern=r"^[a-f0-9]{64}$"),
    ):
        result = fetch(request, mode)
        if expected_forecast_id is not None and expected_forecast_id != result["forecast_id"]:
            raise HTTPException(409, "Forecast changed. Refresh the chart before exporting.")
        return Response(
            pd.DataFrame(result["slots"]).to_csv(index=False),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="gridflex-{mode}.csv"'},
        )

    static = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(static / "index.html")

    return app
