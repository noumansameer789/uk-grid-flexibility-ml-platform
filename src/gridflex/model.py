"""Walk-forward evaluation, split-conformal calibration, and a text-format LightGBM bundle."""

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from gridflex.data import DataQualityError
from gridflex.features import FEATURES, training_features
from gridflex.monitoring import reference_profile

PARAMS = dict(
    n_estimators=220,
    learning_rate=0.045,
    num_leaves=15,
    max_depth=6,
    min_child_samples=100,
    reg_lambda=2.0,
    random_state=42,
    n_jobs=2,
    verbosity=-1,
)


def metrics(y, prediction, lower=None, upper=None) -> dict:
    y, prediction = np.asarray(y), np.asarray(prediction)
    result = {
        "mae": float(np.mean(np.abs(y - prediction))),
        "rmse": float(np.sqrt(np.mean((y - prediction) ** 2))),
    }
    if lower is not None:
        result.update(
            coverage=float(np.mean((y >= lower) & (y <= upper))),
            interval_width=float(np.mean(np.asarray(upper) - np.asarray(lower))),
        )
    return result


def conformal_radius(residuals, alpha: float = 0.1) -> float:
    values = np.sort(np.asarray(residuals, dtype=float))
    if not len(values) or not np.isfinite(values).all() or (values < 0).any() or not 0 < alpha < 1:
        raise ValueError("Finite residuals and alpha in (0,1) are required")
    rank = min(len(values), math.ceil((len(values) + 1) * (1 - alpha)))
    return float(values[rank - 1])


def folds(frame: pd.DataFrame, count: int = 3, days: int = 14):
    final_end = frame.origin.max() + pd.Timedelta(hours=6)
    for i in range(count):
        test_start = final_end - pd.Timedelta(days=(count - i) * days)
        test_end = test_start + pd.Timedelta(days=days)
        calibration_start = test_start - pd.Timedelta(days=days + 1)
        # Purge complete 24h target windows at both boundaries.
        train = frame[
            (frame.timestamp < calibration_start) & (frame.origin < calibration_start - pd.Timedelta(days=1))
        ]
        calibration = frame[
            (frame.origin >= calibration_start) & (frame.origin < test_start - pd.Timedelta(days=1))
        ]
        test = frame[(frame.origin >= test_start) & (frame.origin < test_end)]
        if train.origin.nunique() < 4 * 28 or calibration.empty or test.empty:
            raise DataQualityError("Use at least 100 days of carbon data for the standard backtest")
        yield train, calibration, test


def predict_bundle(bundle: dict, frame: pd.DataFrame) -> pd.DataFrame:
    output = frame[["origin", "timestamp", "horizon"]].copy()
    output["prediction"] = np.clip(bundle["booster"].predict(frame[FEATURES], num_threads=2), 0, 1500)
    radius = bundle["card"]["conformal_radius"]
    output["lower"] = np.maximum(0, output.prediction - radius)
    output["upper"] = output.prediction + radius
    return output


def load_bundle(path: Path) -> dict:
    card = json.loads((path / "model_card.json").read_text())
    model_path = path / "model.txt"
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != card["model_sha256"]:
        raise DataQualityError("Model checksum does not match the model card")
    if card["features"] != FEATURES:
        raise DataQualityError("Incompatible feature contract")
    if not np.isfinite(card["conformal_radius"]) or card["conformal_radius"] < 0:
        raise DataQualityError("Invalid calibration radius")
    booster = lgb.Booster(model_file=str(model_path))
    if booster.feature_name() != FEATURES:
        raise DataQualityError("Native model feature contract mismatch")
    return {"booster": booster, "card": card}


def train(carbon: pd.DataFrame, output: Path, *, data_kind: str, track: bool = False) -> dict:
    from gridflex.evaluation import model_comparison, seasonal_baselines

    if data_kind not in ("real", "synthetic"):
        raise ValueError("Declare data_kind as real or synthetic")
    if (output / "model.txt").exists():
        raise ValueError(
            "Output already contains a model. Use a new candidate directory to preserve existing evidence."
        )
    output.mkdir(parents=True, exist_ok=True)
    gold, feature_report = training_features(carbon)
    gold.to_csv(output / "features.csv", index=False)
    fold_reports, predictions = [], []
    for number, (fit, calibration, test) in enumerate(folds(gold), start=1):
        reg = lgb.LGBMRegressor(**PARAMS).fit(fit[FEATURES], fit.target)
        cal_pred = np.clip(reg.predict(calibration[FEATURES]), 0, 1500)
        radius = conformal_radius(np.abs(calibration.target.to_numpy() - cal_pred))
        pred = np.clip(reg.predict(test[FEATURES]), 0, 1500)
        lower, upper = np.maximum(0, pred - radius), pred + radius
        report = {
            "fold": number,
            "train_end": fit.timestamp.max().isoformat(),
            "calibration_start": calibration.origin.min().isoformat(),
            "calibration_end": calibration.timestamp.max().isoformat(),
            "test_start": test.origin.min().isoformat(),
            "test_end": test.timestamp.max().isoformat(),
            "train_rows": len(fit),
            "test_rows": len(test),
            "radius": radius,
            "lightgbm": metrics(test.target, pred, lower, upper),
            "persistence": metrics(test.target, test.latest),
            "weekly_seasonal": metrics(test.target, test.target_week_lag),
        }
        fold_reports.append(report)
        p = test[["origin", "timestamp", "horizon", "target", "latest", "target_week_lag"]].copy()
        p["prediction"], p["lower"], p["upper"], p["fold"] = pred, lower, upper, number
        predictions.append(p)
    scored = seasonal_baselines(carbon, pd.concat(predictions, ignore_index=True))
    scored.to_csv(output / "backtest_predictions.csv", index=False)
    summary = model_comparison(scored)
    for report in fold_reports:
        report.update(model_comparison(scored[scored.fold == report["fold"]]))
    # Final calibration is held out from the final fit; no refit after estimating its radius.
    cal_start = gold.origin.max() - pd.Timedelta(days=14)
    fit = gold[gold.origin < cal_start - pd.Timedelta(days=1)]
    calibration = gold[gold.origin >= cal_start]
    reg = lgb.LGBMRegressor(**PARAMS).fit(fit[FEATURES], fit.target)
    radius = conformal_radius(
        np.abs(calibration.target - np.clip(reg.predict(calibration[FEATURES]), 0, 1500))
    )
    reg.booster_.save_model(str(output / "model.txt"))
    baseline = min(value["mae"] for name, value in summary.items() if name != "lightgbm")
    gate = summary["lightgbm"]["mae"] < baseline and summary["lightgbm"]["coverage"] >= 0.9
    card = {
        "version": "1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "data_kind": data_kind,
        "algorithm": "LightGBM direct 48-horizon regression",
        "features": FEATURES,
        "training_data_start": str(carbon.timestamp.min()),
        "training_data_end": str(carbon.timestamp.max()),
        "source_rows": len(carbon),
        "data_sha256": hashlib.sha256(carbon.to_csv(index=False).encode()).hexdigest(),
        "model_sha256": hashlib.sha256((output / "model.txt").read_bytes()).hexdigest(),
        "parameters": PARAMS,
        "observation_delay_hours": 2,
        "forecast_horizon_hours": 24,
        "conformal_radius": radius,
        "nominal_coverage": 0.9,
        "feature_report": feature_report,
        "summary": summary,
        "folds": fold_reports,
        "candidate_gate_passed": bool(gate),
        "candidate_gate_policy": "MAE below every baseline and interval coverage at least the nominal 90%; no deployment approval implied",
        "status": "research_candidate" if data_kind == "real" else "synthetic_demo",
        "live_validation": "pending prospective evaluation",
        "limitations": [
            "No guarantee of conformal coverage under temporal distribution shift.",
            "Overlapping forecast horizons create correlated errors.",
            "Historic NESO actuals may be revised; this is a retrospective backtest.",
            "Weather is contextual only; no unavailable future weather is used.",
            "Average grid intensity is not marginal avoided emissions.",
            "Charging recommendations do not control physical equipment.",
        ],
    }
    (output / "model_card.json").write_text(json.dumps(card, indent=2, allow_nan=False))
    (output / "reference.json").write_text(
        json.dumps(
            reference_profile(fit.drop_duplicates("origin"), ["latest", "mean_24h", "std_24h"]), indent=2
        )
    )
    if track:
        import mlflow

        mlflow.set_experiment("uk-grid-flexibility")
        with mlflow.start_run(run_name=f"lightgbm-{data_kind}"):
            mlflow.log_params({**PARAMS, "data_kind": data_kind, "observation_delay_hours": 2})
            for model, measures in summary.items():
                mlflow.log_metrics({f"{model}_{key}": value for key, value in measures.items()})
            mlflow.set_tags({"data_sha256": card["data_sha256"], "model_sha256": card["model_sha256"]})
            for name in ("model_card.json", "model.txt", "reference.json"):
                mlflow.log_artifact(str(output / name))
    return card
