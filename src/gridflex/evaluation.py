"""Fixed post-build diagnostics. These results never tune the fitted model."""

import numpy as np
import pandas as pd

from gridflex.features import OBSERVATION_DELAY, series_from_frame
from gridflex.model import metrics
from gridflex.optimise import ChargingRequest, optimise


def seasonal_baselines(carbon: pd.DataFrame, forecasts: pd.DataFrame) -> pd.DataFrame:
    actual = series_from_frame(carbon)
    output = forecasts.copy()
    eligible = output.origin - OBSERVATION_DELAY - pd.Timedelta(minutes=30)
    candidates = []
    for days in range(1, 9):
        timestamps = output.timestamp - pd.Timedelta(days=days)
        values = actual.reindex(timestamps).to_numpy()
        candidates.append(np.where(timestamps <= eligible, values, np.nan))
    values = np.stack(candidates, axis=1)
    valid = np.isfinite(values)
    if not valid.any(axis=1).all():
        raise ValueError("Seasonal benchmarks lack eligible historical data")
    output["daily_seasonal"] = values[np.arange(len(output)), valid.argmax(axis=1)]
    # At most seven same-clock-time observations, all strictly in the eligible past.
    values[np.cumsum(valid, axis=1) > 7] = np.nan
    output["seven_day_mean"] = np.nanmean(values, axis=1)
    return output


def model_comparison(scored: pd.DataFrame) -> dict:
    columns = {
        "lightgbm": "prediction",
        "persistence": "latest",
        "weekly_seasonal": "target_week_lag",
        "daily_seasonal": "daily_seasonal",
        "seven_day_mean": "seven_day_mean",
    }
    return {
        name: metrics(
            scored.target,
            scored[column],
            scored.lower if name == "lightgbm" else None,
            scored.upper if name == "lightgbm" else None,
        )
        for name, column in columns.items()
    }


def blocked_difference_interval(scored: pd.DataFrame, baseline: str, repetitions=1000) -> dict:
    differences = np.abs(scored.prediction - scored.target) - np.abs(scored[baseline] - scored.target)
    daily = differences.groupby(scored.origin.dt.floor("D")).mean().to_numpy()
    block = min(7, len(daily))
    rng = np.random.default_rng(42)
    draws = []
    for _ in range(repetitions):
        starts = rng.integers(0, len(daily) - block + 1, size=int(np.ceil(len(daily) / block)))
        draw = np.concatenate([daily[start : start + block] for start in starts])[: len(daily)]
        draws.append(float(draw.mean()))
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {
        "mean_mae_difference": float(differences.mean()),
        "lower": float(lo),
        "upper": float(hi),
        "issue_days": len(daily),
        "block_days": block,
        "resamples": repetitions,
        "note": "Exploratory paired moving-block bootstrap; negative favours LightGBM. Limited seasonal coverage; not a significance guarantee.",
    }


def charging_evaluation(scored: pd.DataFrame) -> pd.DataFrame:
    request = ChargingRequest()
    records = []
    for origin, group in scored.groupby("origin", sort=True):
        group = group.sort_values("timestamp")
        if len(group) != 48:
            raise ValueError("Charging evaluation needs a complete issue-time horizon")
        planned = optimise(group, request)
        oracle = optimise(group.assign(prediction=group.target), request)
        energy = np.array([slot["grid_kwh"] for slot in planned["slots"]])
        # Immediate uses the same energy, power and efficiency constraints.
        remaining = request.capacity_kwh * (request.target_soc - request.initial_soc) / request.efficiency
        immediate = np.minimum(
            request.max_charge_kw * 0.5,
            np.maximum(0, remaining - np.arange(48) * request.max_charge_kw * 0.5),
        )
        actual_kg = float(energy @ group.target / 1000)
        immediate_kg = float(immediate @ group.target / 1000)
        records.append(
            {
                "origin": origin,
                "forecast_weighted_kg": planned["carbon_kg"],
                "observed_schedule_proxy_kg": actual_kg,
                "immediate_proxy_kg": immediate_kg,
                "perfect_information_proxy_kg": oracle["carbon_kg"],
                "difference_vs_immediate_kg": actual_kg - immediate_kg,
                "regret_vs_perfect_information_kg": actual_kg - oracle["carbon_kg"],
            }
        )
        for name in ("daily_seasonal", "seven_day_mean"):
            if name in group:
                baseline_plan = optimise(group.assign(prediction=group[name]), request)
                baseline_energy = np.array([slot["grid_kwh"] for slot in baseline_plan["slots"]])
                records[-1][f"{name}_schedule_proxy_kg"] = float(baseline_energy @ group.target / 1000)
    return pd.DataFrame(records)
