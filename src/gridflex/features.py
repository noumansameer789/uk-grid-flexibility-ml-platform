"""Direct multi-horizon features. No target-period actuals or revised NESO forecasts."""

import numpy as np
import pandas as pd

from gridflex.data import DataQualityError, utc

HORIZON = 48
OBSERVATION_DELAY = pd.Timedelta(hours=2)
FEATURES = [
    "latest",
    "day_lag",
    "week_lag",
    "mean_24h",
    "std_24h",
    "trend_2h",
    "target_week_lag",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
    "year_sin",
    "year_cos",
    "horizon",
]


def series_from_frame(frame: pd.DataFrame) -> pd.Series:
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"].map(utc), utc=True)
    if frame.timestamp.duplicated().any():
        raise DataQualityError("Duplicate observations in feature input")
    result = frame.set_index("timestamp").actual.sort_index().astype(float)
    if result.empty or not np.isfinite(result.dropna()).all():
        raise DataQualityError("Empty or non-finite observations")
    if not result.dropna().between(0, 1500).all():
        raise DataQualityError("Carbon observations must be between 0 and 1500 gCO2/kWh")
    if not (result.index == result.index.floor("30min")).all():
        raise DataQualityError("Observations must align to half-hour UTC intervals")
    return result


def forecast_features(actual: pd.Series, origin) -> pd.DataFrame:
    origin = utc(origin)
    if origin != origin.floor("30min"):
        raise DataQualityError("Forecast origin must be on a half hour")
    # A record is eligible only if its interval END is at least two hours old.
    latest_time = origin - OBSERVATION_DELAY - pd.Timedelta(minutes=30)
    history = actual.loc[:latest_time]
    last_day = pd.date_range(latest_time - pd.Timedelta(hours=23, minutes=30), latest_time, freq="30min")
    day = history.reindex(last_day)
    required = [
        latest_time,
        latest_time - pd.Timedelta(days=1),
        latest_time - pd.Timedelta(days=7),
        latest_time - pd.Timedelta(hours=2),
    ]
    values = history.reindex(required)
    if values.isna().any() or day.notna().sum() < 44:
        raise DataQualityError("Insufficient recent history for an as-of forecast")
    targets = pd.date_range(origin, periods=HORIZON, freq="30min")
    week = history.reindex(targets - pd.Timedelta(days=7))
    if week.isna().any():
        raise DataQualityError("Missing weekly seasonal history")
    local = targets.tz_convert("Europe/London")
    hour = local.hour + local.minute / 60
    return pd.DataFrame(
        {
            "origin": origin,
            "timestamp": targets,
            "latest": values.iloc[0],
            "day_lag": values.iloc[1],
            "week_lag": values.iloc[2],
            "mean_24h": day.mean(),
            "std_24h": day.std(),
            "trend_2h": values.iloc[0] - values.iloc[3],
            "target_week_lag": week.to_numpy(),
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "weekday_sin": np.sin(2 * np.pi * local.dayofweek / 7),
            "weekday_cos": np.cos(2 * np.pi * local.dayofweek / 7),
            "year_sin": np.sin(2 * np.pi * local.dayofyear / 365.25),
            "year_cos": np.cos(2 * np.pi * local.dayofyear / 365.25),
            "horizon": np.arange(1, HORIZON + 1),
        }
    )


def training_features(frame: pd.DataFrame, origin_frequency: str = "6h") -> tuple[pd.DataFrame, dict]:
    actual = series_from_frame(frame)
    origins = pd.date_range(
        (actual.index.min() + pd.Timedelta(days=8)).ceil(origin_frequency),
        (actual.index.max() - pd.Timedelta(days=1)).floor(origin_frequency),
        freq=origin_frequency,
    )
    chunks, skipped = [], 0
    for origin in origins:
        try:
            features = forecast_features(actual, origin)
            features["target"] = actual.reindex(features.timestamp).to_numpy()
            if features.target.isna().any():
                raise DataQualityError("Missing target actuals")
            chunks.append(features)
        except DataQualityError:
            skipped += 1
    if not chunks:
        raise DataQualityError("Not enough valid history; at least several weeks are needed")
    return pd.concat(chunks, ignore_index=True), {
        "origins": len(origins),
        "skipped_origins": skipped,
        "observation_delay_hours": 2,
    }
