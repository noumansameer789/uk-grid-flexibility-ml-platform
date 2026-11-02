"""Distribution drift and delayed-label performance, with explicit insufficient-data state."""

import numpy as np
import pandas as pd


def maintenance_exit_code(report: dict, *, advisory_model_alerts: bool = False) -> int:
    """Separate a completed collection run from a model-quality warning.

    The CLI remains strict by default. The scheduled portfolio collector opts
    into advisory model alerts, while source, schema, storage and freshness
    failures remain fatal. Unknown statuses fail closed.
    """
    operational = ("data_freshness", "forecast_issuance", "weather_ingestion")
    if any(report[name]["status"] != "ok" for name in operational):
        return 2
    model_states = [report[name]["status"] for name in ("drift", "performance")]
    allowed = {"ok", "alert", "insufficient_data"}
    if report["status"] not in allowed or any(state not in allowed for state in model_states):
        return 2
    if "alert" in model_states:
        return 0 if advisory_model_alerts else 2
    # Never suppress an aggregate alert that has no recognised model cause.
    return 2 if report["status"] == "alert" else 0


def maintenance_summary(report: dict) -> str:
    """Keep monitoring warnings visible even when the collection job succeeds."""
    lines = [
        "## GridFlex ingestion and monitoring",
        "",
        f"**Execution:** {report['execution_status']}",
        f"**Monitoring:** {report['status']}",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for name in ("data_freshness", "forecast_issuance", "weather_ingestion", "drift", "performance"):
        lines.append(f"| {name.replace('_', ' ')} | {report[name]['status']} |")
    performance = report["performance"]
    if "coverage" in performance:
        lines.extend(
            [
                "",
                f"Interval coverage: **{performance['coverage']:.1%}**; "
                f"target: **{performance['coverage_alert_threshold']:.1%}**.",
                f"MAE: **{performance['mae']:.2f} gCO2/kWh** across "
                f"{performance['distinct_origins']} origins and {performance['target_days']} target days.",
            ]
        )
    lines.extend(
        [
            "",
            "A successful collection run is not evidence that the model passed its quality thresholds. "
            "Model alerts, thresholds and metrics remain unchanged in processed/monitoring.json "
            "inside the run artifact. Overlapping forecast horizons are correlated.",
            "No model was retrained or promoted by this job.",
            "",
        ]
    )
    return "\n".join(lines)


def reference_profile(frame: pd.DataFrame, columns: list[str]) -> dict:
    output = {}
    for col in columns:
        values = frame[col].dropna().to_numpy(dtype=float)
        inner = np.unique(np.quantile(values, np.linspace(0.1, 0.9, 9)))
        edges = np.r_[-np.inf, inner, np.inf]
        counts, _ = np.histogram(values, bins=edges)
        output[col] = {"inner_edges": inner.tolist(), "proportions": (counts / counts.sum()).tolist()}
    return output


def drift_report(frame: pd.DataFrame, reference: dict, min_samples: int = 96) -> dict:
    if len(frame) < min_samples:
        return {"status": "insufficient_data", "samples": len(frame), "features": {}}
    scores = {}
    for col, spec in reference.items():
        if col not in frame:
            continue
        values = frame[col].dropna().to_numpy(dtype=float)
        if len(values) < min_samples or not np.isfinite(values).all():
            continue
        counts, _ = np.histogram(values, bins=np.r_[-np.inf, spec["inner_edges"], np.inf])
        actual = np.clip(counts / counts.sum(), 1e-6, 1)
        expected = np.clip(np.array(spec["proportions"]), 1e-6, 1)
        actual, expected = actual / actual.sum(), expected / expected.sum()
        scores[col] = round(float(np.sum((actual - expected) * np.log(actual / expected))), 5)
    status = "alert" if any(v >= 0.25 for v in scores.values()) else "ok"
    return {
        "status": status if scores else "insufficient_data",
        "samples": len(frame),
        "features": scores,
        "threshold": 0.25,
        "note": "PSI is a heuristic alert, not proof of model failure.",
    }


def performance_report(
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    reference_mae: float,
    min_origins: int = 28,
    min_days: int = 7,
) -> dict:
    if forecasts.duplicated(["origin", "timestamp"]).any():
        raise ValueError("Duplicate issued forecast keys would inflate monitoring evidence")
    joined = forecasts.merge(
        actuals[["timestamp", "actual"]], on="timestamp", how="inner", validate="many_to_one"
    ).dropna(subset=["actual"])
    counts = {
        "scored_forecasts": len(joined),
        "distinct_origins": joined.origin.nunique(),
        "distinct_targets": joined.timestamp.nunique(),
        "target_days": joined.timestamp.dt.floor("D").nunique(),
    }
    if joined.empty:
        return {"status": "insufficient_data", **counts}
    error = np.abs(joined.prediction - joined.actual)
    mae = float(error.mean())
    coverage = float(((joined.actual >= joined.lower) & (joined.actual <= joined.upper)).mean())
    sufficient = counts["distinct_origins"] >= min_origins and counts["target_days"] >= min_days
    baseline_metrics = {}
    for column in ("neso_forecast", "persistence", "weekly_seasonal", "daily_seasonal", "seven_day_mean"):
        if column in joined:
            available = joined.dropna(subset=[column])
            baseline_metrics[column] = (
                {
                    "mae": float(np.abs(available[column] - available.actual).mean()),
                    "scored_forecasts": len(available),
                }
                if len(available)
                else None
            )
    return {
        "status": ("alert" if mae > reference_mae * 1.5 or coverage < 0.9 else "ok")
        if sufficient
        else "insufficient_data",
        **counts,
        "mae": mae,
        "coverage": coverage,
        "mae_alert_threshold": reference_mae * 1.5,
        "coverage_alert_threshold": 0.9,
        "minimum_origins": min_origins,
        "minimum_target_days": min_days,
        "as_issued_baselines": baseline_metrics,
        "note": "Early metrics are descriptive; overlapping horizons are correlated and do not multiply independent evidence.",
    }
