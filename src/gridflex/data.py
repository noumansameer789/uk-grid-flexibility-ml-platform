"""HTTP adapters, immutable raw snapshots, validated silver tables and DuckDB storage."""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import httpx
import numpy as np
import pandas as pd

from gridflex.config import LOCATIONS, WEATHER_VARIABLES, Settings
from gridflex.storage import atomic_text, first_json


class DataQualityError(ValueError):
    pass


class SourceUnavailable(RuntimeError):
    pass


def utc(value) -> pd.Timestamp:
    t = pd.Timestamp(value)
    if t.tzinfo is None:
        raise DataQualityError("A timezone-aware timestamp is required")
    return t.tz_convert("UTC")


def api_time(value) -> str:
    return utc(value).strftime("%Y-%m-%dT%H:%MZ")


def parse_carbon(payload: dict) -> pd.DataFrame:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list) or not payload["data"]:
        raise DataQualityError("NESO response must contain a nonempty data list")
    try:
        rows = [
            {
                "timestamp": utc(x["from"]),
                "end": utc(x["to"]),
                "actual": x["intensity"].get("actual"),
                "forecast": x["intensity"]["forecast"],
            }
            for x in payload["data"]
        ]
        frame = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        for col in ("actual", "forecast"):
            frame[col] = pd.to_numeric(frame[col], errors="raise").astype(float)
            nonnull = frame[col].dropna()
            if not np.isfinite(nonnull).all() or not nonnull.between(0, 1500).all():
                raise DataQualityError(f"Invalid {col} carbon intensity")
        if frame["forecast"].isna().any():
            raise DataQualityError("NESO forecasts cannot be missing")
        if frame["timestamp"].duplicated().any():
            raise DataQualityError("Duplicate carbon intervals")
        if not ((frame["end"] - frame["timestamp"]) == pd.Timedelta(minutes=30)).all():
            raise DataQualityError("Carbon intervals must last exactly 30 minutes")
        if not (frame["timestamp"] == frame["timestamp"].dt.floor("30min")).all():
            raise DataQualityError("Carbon timestamps must align to half hours")
        return frame
    except (KeyError, TypeError, ValueError) as exc:
        raise DataQualityError(f"Invalid NESO schema: {exc}") from exc


def parse_weather(payload: dict, location: str) -> pd.DataFrame:
    try:
        h = payload["hourly"]
        expected_units = {
            "temperature_2m": "°C",
            "wind_speed_10m": "km/h",
            "cloud_cover": "%",
            "shortwave_radiation": "W/m²",
        }
        if any(payload["hourly_units"].get(k) != v for k, v in expected_units.items()):
            raise DataQualityError("Weather units changed")
        if payload.get("utc_offset_seconds", 0) != 0:
            raise DataQualityError("Weather must be requested in UTC")
        frame = pd.DataFrame(
            {"timestamp": pd.to_datetime(h["time"], utc=True), **{v: h[v] for v in WEATHER_VARIABLES}}
        )
        if frame.empty or frame["timestamp"].duplicated().any():
            raise DataQualityError("Empty or duplicate weather intervals")
        if frame.timestamp.isna().any() or not (frame.timestamp == frame.timestamp.dt.floor("h")).all():
            raise DataQualityError("Weather timestamps must be valid whole UTC hours")
        bounds = {
            "temperature_2m": (-80, 60),
            "wind_speed_10m": (0, 400),
            "cloud_cover": (0, 100),
            "shortwave_radiation": (0, 1500),
        }
        for col, (lo, hi) in bounds.items():
            frame[col] = pd.to_numeric(frame[col], errors="raise").astype(float)
            if not np.isfinite(frame[col]).all() or not frame[col].between(lo, hi).all():
                raise DataQualityError(f"Missing or invalid weather: {col}")
        frame["location"] = location
        return frame.sort_values("timestamp").reset_index(drop=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise DataQualityError(f"Invalid Open-Meteo schema: {exc}") from exc


def snapshot(root: Path, source: str, payload: dict, request: dict) -> str:
    """Content addressing makes retries idempotent without overwriting raw evidence."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(body.encode()).hexdigest()
    folder = root / "raw" / source
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest}.json"
    first_json(
        path,
        {
            "retrieved_at": datetime.now(UTC).isoformat(),
            "request": request,
            "sha256": digest,
            "payload": payload,
        },
    )
    return digest


class Sources:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.settings = settings or Settings()
        self.client = client or httpx.Client(
            timeout=self.settings.timeout, headers={"User-Agent": "GridFlexPortfolio/1.0"}
        )

    def close(self):
        self.client.close()

    def get(self, url: str, params: dict | None = None) -> dict:
        last = None
        for attempt in range(3):
            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise DataQualityError("Expected a JSON object")
                return result
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    break
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt))
        raise SourceUnavailable(f"Source request failed: {url.split('?')[0]}") from last

    def carbon(self, start, end, save: bool = True) -> pd.DataFrame:
        start, end = utc(start), utc(end)
        if start != start.floor("30min") or end != end.floor("30min"):
            raise ValueError("Carbon request boundaries must align to half hours")
        if end <= start or end - start > pd.Timedelta(days=730):
            raise ValueError("Request between 1 interval and 730 days")
        frames = []
        cursor = start
        while cursor < end:
            stop = min(cursor + pd.Timedelta(days=14), end)
            url = f"{self.settings.carbon_url}/intensity/{api_time(cursor)}/{api_time(stop)}"
            payload = self.get(url)
            frame = parse_carbon(payload)
            if save:
                snapshot(self.settings.data_dir, "neso", payload, {"url": url})
            frames.append(frame)
            cursor = stop
        result = pd.concat(frames).drop_duplicates("timestamp", keep="last").sort_values("timestamp")
        result = result[(result.timestamp >= start) & (result.timestamp < end)].reset_index(drop=True)
        expected = pd.date_range(start, end, freq="30min", inclusive="left")
        if not pd.DatetimeIndex(result.timestamp).equals(expected):
            raise DataQualityError("Source returned an incomplete requested carbon interval range")
        return result

    def weather(self, start=None, end=None, save: bool = True) -> pd.DataFrame:
        archive = start is not None
        url = self.settings.archive_url if archive else self.settings.weather_url
        frames = []
        for name, (lat, lon) in LOCATIONS.items():
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": ",".join(WEATHER_VARIABLES),
                "timezone": "UTC",
                "wind_speed_unit": "kmh",
            }
            if archive:
                params.update(start_date=str(start)[:10], end_date=str(end)[:10])
            else:
                params.update(forecast_days=2, past_days=1)
            payload = self.get(url, params)
            frames.append(parse_weather(payload, name))
            if save:
                snapshot(self.settings.data_dir, "open-meteo", payload, {"url": url, "params": params})
        return pd.concat(frames, ignore_index=True)


def quality_report(carbon: pd.DataFrame) -> dict:
    if carbon.empty:
        raise DataQualityError("No carbon records")
    expected = pd.date_range(carbon.timestamp.min(), carbon.timestamp.max(), freq="30min")
    missing = expected.difference(pd.DatetimeIndex(carbon.timestamp))
    return {
        "rows": len(carbon),
        "start": carbon.timestamp.min().isoformat(),
        "end": carbon.end.max().isoformat(),
        "missing_intervals": len(missing),
        "missing_actuals": int(carbon.actual.isna().sum()),
        "coverage": round(len(carbon) / len(expected), 6),
    }


def silver(carbon: pd.DataFrame, weather: pd.DataFrame | None = None) -> pd.DataFrame:
    frame = carbon.copy()
    if weather is not None and not weather.empty:
        # All three locations must be present; this is a simple unweighted context index.
        counts = weather.groupby("timestamp").location.nunique()
        full = counts[counts == len(LOCATIONS)].index
        agg = weather[weather.timestamp.isin(full)].groupby("timestamp")[WEATHER_VARIABLES].mean()
        agg = agg.resample("30min").ffill(limit=1)
        frame = frame.merge(agg, left_on="timestamp", right_index=True, how="left", validate="one_to_one")
    return frame


def save_silver(frame: pd.DataFrame, root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    (root / "processed").mkdir(exist_ok=True)
    report = quality_report(frame)
    incoming = frame.copy()
    for column in WEATHER_VARIABLES:
        if column not in incoming:
            incoming[column] = float("nan")
    with duckdb.connect(str(root / "gridflex.duckdb")) as con:
        con.execute("SET TimeZone='UTC'")
        con.register("incoming", incoming)
        # Rebuild from keyed union in one transaction, preserving any already observed actuals.
        con.execute("BEGIN")
        con.execute(
            'CREATE TABLE IF NOT EXISTS silver_grid AS SELECT timestamp, "end", actual, forecast FROM incoming WHERE false'
        )
        con.execute("""CREATE OR REPLACE TABLE silver_grid AS
          SELECT coalesce(n.timestamp, o.timestamp) AS timestamp,
                 coalesce(n."end", o."end") AS "end",
                 coalesce(n.actual, o.actual) AS actual,
                 coalesce(n.forecast, o.forecast) AS forecast
          FROM silver_grid o FULL OUTER JOIN incoming n USING (timestamp)
          ORDER BY timestamp""")
        con.execute("CREATE TABLE IF NOT EXISTS silver_context AS SELECT * FROM incoming WHERE false")
        # Upgrade older databases and preserve historical context on carbon-only refreshes.
        for column in WEATHER_VARIABLES:
            con.execute(f'ALTER TABLE silver_context ADD COLUMN IF NOT EXISTS "{column}" DOUBLE')
        columns = ["end", "actual", "forecast", *WEATHER_VARIABLES]
        expressions = ", ".join(f'coalesce(n."{c}", o."{c}") AS "{c}"' for c in columns)
        con.execute(f"""CREATE OR REPLACE TABLE silver_context AS
          SELECT coalesce(n.timestamp, o.timestamp) AS timestamp, {expressions}
          FROM silver_context o FULL OUTER JOIN incoming n USING (timestamp)
          ORDER BY timestamp""")
        con.execute("COMMIT")
        merged = con.execute("SELECT * FROM silver_grid ORDER BY timestamp").df()
        context = con.execute("SELECT * FROM silver_context ORDER BY timestamp").df()
    atomic_text(root / "processed" / "carbon.csv", merged.to_csv(index=False))
    atomic_text(root / "processed" / "context.csv", context.to_csv(index=False))
    atomic_text(root / "processed" / "quality.json", json.dumps(report, indent=2))
    return report
