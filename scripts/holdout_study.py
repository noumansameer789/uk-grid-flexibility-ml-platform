"""Freeze a residual LightGBM candidate before fetching a later temporal holdout.

Run develop first, then holdout. Existing walk-forward folds are development data.
No holdout-driven hyperparameter search or overwrite of the original model bundle.
"""

import argparse
import hashlib
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from gridflex.config import Settings
from gridflex.data import Sources
from gridflex.evaluation import blocked_difference_interval, seasonal_baselines
from gridflex.features import FEATURES, training_features
from gridflex.model import PARAMS, conformal_radius, folds, load_bundle, metrics

OUT = Path("reports/temporal_holdout")
EXTRA = ["seven_day_mean", "daily_seasonal", "latest_minus_daily", "latest_minus_week"]
INPUTS = FEATURES + EXTRA
END = pd.Timestamp("2026-09-21T00:00Z")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dataset(carbon):
    gold, _ = training_features(carbon)
    gold = seasonal_baselines(carbon, gold)
    gold["latest_minus_daily"] = gold.latest - gold.day_lag
    gold["latest_minus_week"] = gold.latest - gold.week_lag
    return gold


def candidate(fit):
    return lgb.LGBMRegressor(**PARAMS).fit(fit[INPUTS], fit.target - fit.seven_day_mean)


def prediction(model, rows):
    return np.clip(rows.seven_day_mean.to_numpy() + model.predict(rows[INPUTS]), 0, 1500)


def develop():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "protocol.json").exists():
        raise SystemExit("Protocol already frozen; preserve it and use a new study directory.")
    carbon = pd.read_csv("data/reference/carbon.csv")
    carbon["timestamp"] = pd.to_datetime(carbon.timestamp, utc=True)
    assert carbon.timestamp.max() < END
    gold = dataset(carbon)
    rows, development = [], []
    for number, (fit, _calibration, test) in enumerate(folds(gold), 1):
        model = candidate(fit)
        pred = prediction(model, test)
        development.append(
            {
                "fold": number,
                "candidate": metrics(test.target, pred),
                "seven_day_mean": metrics(test.target, test.seven_day_mean),
            }
        )
        rows.append(test.assign(prediction=pred))
    scored = pd.concat(rows)
    cal_start = gold.origin.max() - pd.Timedelta(days=14)
    fit = gold[(gold.origin < cal_start - pd.Timedelta(days=1)) & (gold.timestamp < cal_start)]
    calibration = gold[gold.origin >= cal_start]
    model = candidate(fit)
    model.booster_.save_model(str(OUT / "candidate.txt"))
    base_radius = conformal_radius(np.abs(calibration.target - calibration.seven_day_mean))
    radius = conformal_radius(np.abs(calibration.target - prediction(model, calibration)))
    protocol = {
        "frozen_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "development_end_exclusive": END.isoformat(),
        "holdout_start": END.isoformat(),
        "holdout_end_exclusive": "2026-10-11T00:00:00+00:00",
        "development_data_sha256": digest("data/reference/carbon.csv"),
        "candidate_sha256": digest(OUT / "candidate.txt"),
        "candidate": "LightGBM correction to seven-day same-clock mean",
        "features": INPUTS,
        "parameters": PARAMS,
        "candidate_radius": radius,
        "baseline_radius": base_radius,
        "training_target_end": fit.timestamp.max().isoformat(),
        "calibration_target_end": calibration.timestamp.max().isoformat(),
        "development_results": development,
        "development_aggregate": {
            "candidate": metrics(scored.target, scored.prediction),
            "seven_day_mean": metrics(scored.target, scored.seven_day_mean),
        },
        "policy": "One fixed candidate; no holdout tuning. Promotion requires lower MAE than every baseline, paired 7-day bootstrap upper difference below zero, and coverage >= 90%.",
        "limitations": [
            "Retrospective later-period test, not prospective operation.",
            "Historical actuals may be revised; first-published vintages unavailable.",
            "Overlapping horizons; short seasonal span; block interval exploratory.",
        ],
    }
    (OUT / "protocol.json").write_text(json.dumps(protocol, indent=2, allow_nan=False))
    print(json.dumps(protocol["development_aggregate"], indent=2), flush=True)


def holdout():
    protocol = json.loads((OUT / "protocol.json").read_text())
    assert digest(OUT / "candidate.txt") == protocol["candidate_sha256"]
    if (OUT / "results.json").exists():
        raise SystemExit("Holdout already scored. Preserve results rather than retuning.")
    source = Sources(Settings(data_dir=OUT / "data"))
    future = source.carbon(
        pd.Timestamp(protocol["holdout_start"]), pd.Timestamp(protocol["holdout_end_exclusive"])
    )
    future.to_csv(OUT / "observations.csv", index=False)
    old = pd.read_csv("data/reference/carbon.csv")
    old["timestamp"] = pd.to_datetime(old.timestamp, utc=True)
    all_data = pd.concat([old, future], ignore_index=True)
    gold = dataset(all_data)
    test = gold[gold.origin >= END].copy()
    reg = lgb.Booster(model_file=str(OUT / "candidate.txt"))
    test["prediction"] = prediction(reg, test)
    original = load_bundle(Path("models/production"))
    test["original_lightgbm"] = np.clip(original["booster"].predict(test[FEATURES], num_threads=2), 0, 1500)
    summary = {}
    for name, column, radius in [
        ("residual_lightgbm", "prediction", protocol["candidate_radius"]),
        ("original_lightgbm", "original_lightgbm", original["card"]["conformal_radius"]),
        ("seven_day_mean", "seven_day_mean", protocol["baseline_radius"]),
        ("persistence", "latest", None),
        ("weekly_seasonal", "target_week_lag", None),
        ("daily_seasonal", "daily_seasonal", None),
    ]:
        pred = test[column]
        summary[name] = metrics(
            test.target,
            pred,
            None if radius is None else np.maximum(0, pred - radius),
            None if radius is None else pred + radius,
        )
    baselines = ["seven_day_mean", "persistence", "weekly_seasonal", "daily_seasonal"]
    strongest = min(baselines, key=lambda name: summary[name]["mae"])
    column = {"persistence": "latest", "weekly_seasonal": "target_week_lag"}.get(strongest, strongest)
    interval = blocked_difference_interval(test, column)
    passed = (
        summary["residual_lightgbm"]["mae"] < summary[strongest]["mae"]
        and summary["residual_lightgbm"]["coverage"] >= 0.9
        and interval["upper"] < 0
    )
    result = {
        "evaluated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "protocol_sha256": digest(OUT / "protocol.json"),
        "observations_sha256": digest(OUT / "observations.csv"),
        "new_observations": len(future),
        "forecast_origins": test.origin.nunique(),
        "forecast_target_rows": len(test),
        "first_origin": test.origin.min().isoformat(),
        "last_target": test.timestamp.max().isoformat(),
        "metrics": summary,
        "strongest_baseline": strongest,
        "paired_block_interval": interval,
        "promotion_gate_passed": bool(passed),
        "live_demo_model": "seven_day_mean",
        "limitations": protocol["limitations"],
    }
    test.to_csv(OUT / "predictions.csv", index=False)
    (OUT / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps(result, indent=2), flush=True)


def verify():
    """Recompute saved predictions and metrics without fetching or fitting anything."""
    protocol = json.loads((OUT / "protocol.json").read_text())
    result = json.loads((OUT / "results.json").read_text())
    assert digest(OUT / "protocol.json") == result["protocol_sha256"]
    assert digest(OUT / "observations.csv") == result["observations_sha256"]
    assert digest(OUT / "candidate.txt") == protocol["candidate_sha256"]
    assert digest("data/reference/carbon.csv") == protocol["development_data_sha256"]
    test = pd.read_csv(OUT / "predictions.csv")
    reg = lgb.Booster(model_file=str(OUT / "candidate.txt"))
    original = load_bundle(Path("models/production"))
    np.testing.assert_allclose(prediction(reg, test), test.prediction, rtol=1e-10)
    np.testing.assert_allclose(
        np.clip(original["booster"].predict(test[FEATURES], num_threads=2), 0, 1500),
        test.original_lightgbm,
        rtol=1e-10,
    )
    for name, column, radius in [
        ("residual_lightgbm", "prediction", protocol["candidate_radius"]),
        ("original_lightgbm", "original_lightgbm", original["card"]["conformal_radius"]),
        ("seven_day_mean", "seven_day_mean", protocol["baseline_radius"]),
        ("persistence", "latest", None),
        ("weekly_seasonal", "target_week_lag", None),
        ("daily_seasonal", "daily_seasonal", None),
    ]:
        pred = test[column]
        measured = metrics(
            test.target,
            pred,
            None if radius is None else np.maximum(0, pred - radius),
            None if radius is None else pred + radius,
        )
        for key, value in measured.items():
            np.testing.assert_allclose(value, result["metrics"][name][key], rtol=1e-10)
    assert len(test) == result["forecast_target_rows"]
    print("Frozen model predictions, six-model metrics and input digests verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["develop", "holdout", "verify"])
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.output
    {"develop": develop, "holdout": holdout, "verify": verify}[args.stage]()
