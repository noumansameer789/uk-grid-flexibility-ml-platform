"""Recompute scientific audit from committed observations and out-of-fold predictions."""

import json
from pathlib import Path

import pandas as pd

from gridflex.cli import read_carbon
from gridflex.evaluation import (
    blocked_difference_interval,
    charging_evaluation,
    model_comparison,
    seasonal_baselines,
)
from gridflex.storage import atomic_text

root = Path(__file__).resolve().parents[1]
destination = root / "docs/evidence"
scored = pd.read_csv(destination / "backtest_predictions.csv.gz", parse_dates=["origin", "timestamp"])
scored = seasonal_baselines(read_carbon(root / "data/reference/carbon.csv"), scored)
summary = model_comparison(scored)
charging = charging_evaluation(scored)
charging.to_csv(destination / "charging-evaluation.csv", index=False)
scored.to_csv(
    destination / "extended-backtest.csv.gz", index=False, compression={"method": "gzip", "mtime": 0}
)
best = min((key for key in summary if key != "lightgbm"), key=lambda k: summary[k]["mae"])
baseline_columns = {
    "persistence": "latest",
    "weekly_seasonal": "target_week_lag",
    "daily_seasonal": "daily_seasonal",
    "seven_day_mean": "seven_day_mean",
}
horizons = {}
for start, end in [(1, 12), (13, 24), (25, 36), (37, 48)]:
    horizons[f"{(start - 1) / 2:g}–{end / 2:g}h"] = model_comparison(
        scored[scored.horizon.between(start, end)]
    )
report = {
    "protocol": "Post-build diagnostics; fitted weights, features and calibration untouched. No model selection on these added comparisons.",
    "summary": summary,
    "best_baseline": best,
    "horizon_metrics": horizons,
    "paired_difference": blocked_difference_interval(scored, baseline_columns[best]),
    "charging": {
        "simulated_origins": len(charging),
        "mean_schedule_proxy_kg": float(charging.observed_schedule_proxy_kg.mean()),
        "mean_immediate_proxy_kg": float(charging.immediate_proxy_kg.mean()),
        "mean_regret_kg": float(charging.regret_vs_perfect_information_kg.mean()),
        "baseline_schedule_proxy_means_kg": {
            name: float(charging[f"{name}_schedule_proxy_kg"].mean())
            for name in ("daily_seasonal", "seven_day_mean")
        },
        "fraction_better_than_immediate": float((charging.difference_vs_immediate_kg < 0).mean()),
        "aggregate_proxy_reduction_pct": float(
            100 * (1 - charging.observed_schedule_proxy_kg.sum() / charging.immediate_proxy_kg.sum())
        ),
        "note": "Fixed default battery on overlapping historical horizons. Simulated average-intensity proxy; no actual charging or avoided-emissions claim.",
    },
}
atomic_text(destination / "scientific-audit.json", json.dumps(report, indent=2))
# Update the evidence and decision rule without changing trained weights or the interval radius.
card_path = root / "models/production/model_card.json"
card = json.loads(card_path.read_text())
card["summary"] = summary
for fold in card["folds"]:
    fold.update(model_comparison(scored[scored.fold == fold["fold"]]))
card["candidate_gate_passed"] = bool(
    summary["lightgbm"]["mae"] < summary[best]["mae"]
    and summary["lightgbm"]["coverage"] >= card["nominal_coverage"]
)
card["candidate_gate_policy"] = (
    "MAE below every baseline and coverage at least nominal 90%; no deployment approval implied"
)
card["audit_protocol"] = report["protocol"]
atomic_text(card_path, json.dumps(card, indent=2))
print(json.dumps(report, indent=2))
