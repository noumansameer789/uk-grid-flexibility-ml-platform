import hashlib
import json
import logging
import threading
import time
from datetime import UTC, datetime

import pandas as pd

from gridflex.config import LOCATIONS, Settings
from gridflex.data import DataQualityError, Sources, SourceUnavailable
from gridflex.evaluation import seasonal_baselines
from gridflex.features import forecast_features, series_from_frame
from gridflex.model import load_bundle, predict_bundle
from gridflex.storage import first_json, read_json

log = logging.getLogger("gridflex")


class ForecastService:
    def __init__(self, settings: Settings, sources: Sources | None = None, clock=None):
        self.settings = settings
        self.sources = sources or Sources(settings)
        self.bundle = load_bundle(settings.model_dir)
        self._cache = {}
        self._lock = threading.Lock()
        self.last_error = None
        self.clock = clock or (lambda: pd.Timestamp.now(tz="UTC"))
        self._failures = {}

    def forecast(self, mode: str = "replay") -> dict:
        if mode == "replay":
            result = read_json(self.settings.model_dir / "replay.json")
            if result["model_sha256"] != self.bundle["card"]["model_sha256"]:
                raise DataQualityError("Replay and loaded model do not match")
            # Gate policy is current metadata; saved predictions are unchanged.
            result["candidate_gate_passed"] = self.bundle["card"]["candidate_gate_passed"]
            result["forecast_id"] = forecast_id(result)
            return result
        if mode != "live":
            raise ValueError("Choose replay or live")
        with self._lock:
            cached = self._cache.get("live")
            now = self.clock()
            origin = (now + pd.Timedelta(seconds=1)).ceil("30min")
            if (
                cached
                and cached[0] + self.settings.cache_seconds > time.monotonic()
                and cached[1]["origin"] == origin.isoformat()
            ):
                return cached[1]
            path = (
                self.settings.data_dir
                / "issued"
                / (f"{origin.strftime('%Y%m%dT%H%MZ')}_{self.bundle['card']['model_sha256'][:16]}.json")
            )
            if path.exists():
                result = read_json(path)
                self.validate_saved(result, origin)
                self._cache["live"] = (time.monotonic(), result)
                return result
            if self._failures.get("live", 0) > time.monotonic():
                raise SourceUnavailable("Upstream retry cooldown is active")
            try:
                carbon = self.sources.carbon(origin - pd.Timedelta(days=9), origin + pd.Timedelta(days=1))
                features = forecast_features(series_from_frame(carbon), origin)
                if self.bundle["card"]["data_kind"] != "real":
                    raise DataQualityError("Live forecasts require a model trained on real data")
                predictions = seasonal_baselines(carbon, predict_bundle(self.bundle, features))
                predictions["persistence"] = features.latest.to_numpy()
                predictions["weekly_seasonal"] = features.target_week_lag.to_numpy()
                official = carbon.set_index("timestamp").forecast.reindex(predictions.timestamp)
                predictions["neso_forecast"] = official.to_numpy()
                if predictions.neso_forecast.isna().any():
                    raise DataQualityError("Incomplete official forecast horizon")
                result = forecast_payload(predictions, "live", self.bundle["card"])
                result["retrieved_at"] = datetime.now(UTC).isoformat()
                result["issued_at"] = self.clock().isoformat()
                if self.clock() >= origin:
                    raise SourceUnavailable("The source request crossed the forecast start; refresh to retry")
                result["last_actual_at"] = carbon.dropna(subset=["actual"]).timestamp.max().isoformat()
                result["latest_eligible_actual_at"] = (origin - pd.Timedelta(hours=2, minutes=30)).isoformat()
                # Append immutable issued forecasts for later scoring. No model promotion occurs here.
                result["forecast_id"] = forecast_id(result)
                result = first_json(path, result)
                self.validate_saved(result, origin)
                self._cache["live"] = (time.monotonic(), result)
                self.last_error = None
                self._failures.pop("live", None)
                return result
            except Exception as exc:
                self.last_error = type(exc).__name__
                self._failures["live"] = time.monotonic() + self.settings.failure_cache_seconds
                log.warning("live_forecast_failed", extra={"error_type": self.last_error})
                raise

    def validate_saved(self, result, origin):
        try:
            valid = (
                result["mode"] == "live"
                and result["origin"] == origin.isoformat()
                and result["model_sha256"] == self.bundle["card"]["model_sha256"]
                and result["forecast_id"] == forecast_id(result)
                and pd.Timestamp(result["issued_at"]) < origin
            )
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise DataQualityError("Saved forecast integrity check failed")

    def weather(self) -> dict:
        with self._lock:
            cached = self._cache.get("weather")
            if cached and cached[0] + 3600 > time.monotonic():
                return cached[1]
            if self._failures.get("weather", 0) > time.monotonic():
                raise SourceUnavailable("Weather retry cooldown is active")
            try:
                frame = self.sources.weather(save=False)
                now = self.clock().floor("h")
                frame = frame[frame.timestamp == now]
                if len(frame) != len(LOCATIONS) or set(frame.location) != set(LOCATIONS):
                    raise DataQualityError(
                        "Weather response does not contain the current hour for all locations"
                    )
            except Exception:
                self._failures["weather"] = time.monotonic() + self.settings.failure_cache_seconds
                raise
            result = {
                "timestamp": now.isoformat(),
                "source": "Open-Meteo operational model",
                "locations": json.loads(frame.to_json(orient="records", date_format="iso")),
                "note": "Context only; these weather forecasts are not inputs to the current carbon model.",
            }
            self._cache["weather"] = (time.monotonic(), result)
            self._failures.pop("weather", None)
            return result


def forecast_id(payload: dict) -> str:
    evidence = {key: payload[key] for key in ("mode", "origin", "model_sha256", "slots")}
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, allow_nan=False).encode()).hexdigest()


def forecast_payload(frame: pd.DataFrame, mode: str, card: dict) -> dict:
    return {
        "mode": mode,
        "origin": frame.origin.iloc[0].isoformat(),
        "units": "gCO2/kWh",
        "source": "LightGBM research candidate",
        "nominal_coverage": card["nominal_coverage"],
        "model_sha256": card["model_sha256"],
        "candidate_gate_passed": card["candidate_gate_passed"],
        "training_data_end": card["training_data_end"],
        "notice": "Historical replay, not a current forecast."
        if mode == "replay"
        else "Research forecast; prospective validation is still accumulating.",
        "slots": json.loads(frame.to_json(orient="records", date_format="iso")),
    }
