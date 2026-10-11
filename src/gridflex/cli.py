import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from gridflex.config import Settings
from gridflex.data import (
    DataQualityError,
    Sources,
    SourceUnavailable,
    quality_report,
    save_silver,
    silver,
    utc,
)
from gridflex.features import forecast_features, series_from_frame, training_features
from gridflex.model import load_bundle, predict_bundle, train
from gridflex.monitoring import drift_report, performance_report
from gridflex.service import ForecastService, forecast_payload
from gridflex.storage import StorageUnavailable, atomic_text, read_json


def read_carbon(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    for col in ("timestamp", "end"):
        frame[col] = pd.to_datetime(frame[col].map(utc), utc=True)
    if not ((frame.end - frame.timestamp) == pd.Timedelta(minutes=30)).all():
        raise DataQualityError("CSV intervals must last exactly 30 minutes")
    series_from_frame(frame)
    return frame


def monitor(settings: Settings) -> dict:
    bundle = load_bundle(settings.model_dir)
    carbon = read_carbon(settings.data_dir / "processed" / "carbon.csv")
    gold, feature_report = training_features(carbon.tail(30 * 48))
    reference = json.loads((settings.model_dir / "reference.json").read_text())
    # One distribution sample per origin, rather than 48 duplicated history rows.
    unique = gold.drop_duplicates("origin")
    drift = drift_report(unique, reference, min_samples=48)
    issued = []
    for path in sorted((settings.data_dir / "issued").glob("*.json")):
        entry = read_json(path)
        if entry.get("model_sha256") == bundle["card"]["model_sha256"]:
            issued_at = utc(entry.get("issued_at") or entry.get("retrieved_at"))
            if issued_at > pd.Timestamp(entry["origin"]):
                raise DataQualityError("Saved forecast was issued after its declared start")
            rows = pd.DataFrame(entry["slots"])
            rows["issued_at"] = issued_at
            issued.append(rows)
    if issued:
        forecasts = pd.concat(issued, ignore_index=True)
        forecasts["timestamp"] = pd.to_datetime(forecasts.timestamp, utc=True)
        forecasts["origin"] = pd.to_datetime(forecasts.origin, utc=True)
        forecasts = forecasts.sort_values("issued_at").drop_duplicates(["origin", "timestamp"], keep="first")
        forecasts = forecasts[forecasts.timestamp >= carbon.timestamp.max() - pd.Timedelta(days=7)]
        performance = performance_report(forecasts, carbon, bundle["card"]["summary"]["lightgbm"]["mae"])
    else:
        performance = {"status": "insufficient_data", "scored_forecasts": 0}
    latest_actual_end = carbon.dropna(subset=["actual"]).end.max()
    actual_age = (pd.Timestamp.now(tz="UTC") - latest_actual_end).total_seconds()
    freshness = {
        "status": "alert" if actual_age > 2.5 * 3600 else "ok",
        "latest_actual_end": latest_actual_end.isoformat(),
        "age_hours": round(actual_age / 3600, 2),
        "maximum_age_hours": 2.5,
    }
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model_sha256": bundle["card"]["model_sha256"],
        "drift_reference_sha256": hashlib.sha256(
            (settings.model_dir / "reference.json").read_bytes()
        ).hexdigest(),
        "drift": drift,
        "performance": performance,
        "data_freshness": freshness,
        "data_quality": quality_report(carbon),
        "feature_quality": feature_report,
        "status": "alert"
        if "alert" in (drift["status"], performance["status"], freshness["status"])
        else "insufficient_data"
        if "insufficient_data" in (drift["status"], performance["status"])
        else "ok",
    }
    atomic_text(settings.data_dir / "processed" / "monitoring.json", json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description="GridFlex: auditable carbon forecasting and charging")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--start", required=True, help="UTC timestamp, inclusive")
    ingest.add_argument("--end", required=True, help="UTC timestamp, exclusive")
    ingest.add_argument(
        "--weather", action="store_true", help="Archive weather; end must be at least 5 days ago"
    )
    training = sub.add_parser("train")
    training.add_argument("--input", type=Path, default=Path("data/processed/carbon.csv"))
    training.add_argument("--output", type=Path, default=Path("artifacts/new-candidate"))
    training.add_argument("--data-kind", choices=["real", "synthetic"], required=True)
    training.add_argument("--track", action="store_true")
    replay = sub.add_parser("replay")
    replay.add_argument("--origin", required=True)
    replay.add_argument("--input", type=Path, required=True)
    sub.add_parser("forecast")
    sub.add_parser("maintenance")
    check = sub.add_parser("monitor")
    check.add_argument("--fail-on-alert", action="store_true")
    server = sub.add_parser("serve")
    server.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    settings = Settings()
    if args.command == "ingest":
        source = Sources(settings)
        try:
            carbon = source.carbon(args.start, args.end)
            weather = (
                source.weather(
                    args.start[:10], (pd.Timestamp(args.end) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                )
                if args.weather
                else None
            )
            print(json.dumps(save_silver(silver(carbon, weather), settings.data_dir), indent=2))
        finally:
            source.close()
    elif args.command == "train":
        if args.track:
            import mlflow

            os.environ.setdefault("MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR", "false")
            mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
        card = train(read_carbon(args.input), args.output, data_kind=args.data_kind, track=args.track)
        print(json.dumps(card["summary"], indent=2))
    elif args.command == "replay":
        bundle = load_bundle(settings.model_dir)
        frame = read_carbon(args.input)
        if pd.Timestamp(args.origin) <= pd.Timestamp(bundle["card"]["training_data_end"]):
            parser.error("Replay origin must be after all training and calibration data")
        pred = predict_bundle(bundle, forecast_features(series_from_frame(frame), args.origin))
        actuals = frame.set_index("timestamp")
        for name, source in (("actual", "actual"), ("neso_forecast", "forecast")):
            pred[name] = actuals[source].reindex(pred.timestamp).to_numpy()
        result = forecast_payload(pred, "replay", bundle["card"])
        result["neso_forecast_note"] = (
            "Historical provider values may have been revised; not a fair as-issued benchmark."
        )
        atomic_text(settings.model_dir / "replay.json", json.dumps(result, indent=2, allow_nan=False))
        print("Historical replay created")
    elif args.command == "forecast":
        service = ForecastService(settings)
        try:
            print(json.dumps(service.forecast("live"), indent=2))
        finally:
            service.sources.close()
    elif args.command == "monitor":
        result = monitor(settings)
        print(json.dumps(result, indent=2))
        if args.fail_on_alert and result["status"] == "alert":
            raise SystemExit(2)
    elif args.command == "maintenance":
        now = pd.Timestamp.now(tz="UTC").floor("30min")
        source = Sources(settings)
        try:
            carbon = source.carbon(now - pd.Timedelta(days=30), now)
            weather_error = None
            try:
                weather = source.weather()
            except (SourceUnavailable, DataQualityError) as exc:
                weather = None
                weather_error = type(exc).__name__
            save_silver(silver(carbon, weather), settings.data_dir)
        finally:
            source.close()
        service = ForecastService(settings)
        forecast_error = None
        try:
            service.forecast("live")
        except (SourceUnavailable, DataQualityError, StorageUnavailable) as exc:
            forecast_error = {"error_type": type(exc).__name__, "detail": str(exc)}
        finally:
            service.sources.close()
        result = monitor(settings)
        result["forecast_issuance"] = {
            "status": "degraded" if forecast_error else "ok",
            "error": forecast_error,
        }
        result["weather_ingestion"] = {
            "status": "degraded" if weather_error else "ok",
            "error_type": weather_error,
        }
        if weather_error or forecast_error:
            result["status"] = "alert"
        atomic_text(settings.data_dir / "processed" / "monitoring.json", json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        if result["status"] == "alert":
            raise SystemExit(2)
    elif args.command == "serve":
        import uvicorn

        uvicorn.run(
            "gridflex.api:create_app",
            factory=True,
            host="0.0.0.0",
            port=args.port,
            limit_concurrency=64,
            backlog=128,
            timeout_keep_alive=5,
        )


if __name__ == "__main__":
    main()
