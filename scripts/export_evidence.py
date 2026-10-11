"""Package measured run evidence. Run after training; does not invent results."""

import gzip
import hashlib
import json
import shutil
from pathlib import Path

import mlflow
import pandas as pd

root = Path(__file__).resolve().parents[1]
model = root / "models" / "production"
output = root / "docs" / "evidence"
output.mkdir(parents=True, exist_ok=True)
card = json.loads((model / "model_card.json").read_text())
predictions = pd.read_csv(model / "backtest_predictions.csv")
with gzip.GzipFile(filename=str(output / "backtest_predictions.csv.gz"), mode="wb", mtime=0) as f:
    f.write(predictions.to_csv(index=False).encode())
shutil.copy2(root / "data" / "processed" / "quality.json", output / "latest_ingestion_quality.json")
sources = []
for path in sorted((root / "data" / "raw").glob("*/*.json")):
    raw = json.loads(path.read_text())
    sources.append(
        {
            "source": path.parent.name,
            "retrieved_at": raw["retrieved_at"],
            "request": raw["request"],
            "payload_sha256": raw["sha256"],
        }
    )
manifest = {
    "source_snapshots": sources,
    "committed_training_csv_sha256": hashlib.sha256(
        (root / "data/reference/carbon.csv").read_bytes()
    ).hexdigest(),
    "model_sha256": card["model_sha256"],
}
(output / "data_manifest.json").write_text(json.dumps(manifest, indent=2))
mlflow.set_tracking_uri("sqlite:///mlflow.db")
runs = mlflow.search_runs(experiment_names=["uk-grid-flexibility"])
columns = [
    c
    for c in runs
    if c.startswith(("metrics.", "params.", "tags.data_", "tags.model_"))
    or c in ("run_id", "status", "start_time", "end_time")
]
runs[columns].to_json(output / "mlflow_runs.json", orient="records", date_format="iso", indent=2)
lines = [
    "# Measured backtest",
    "",
    "Generated from the saved model card; all values use real NESO observations.",
    "",
    "| Model | MAE (gCO₂/kWh) | RMSE (gCO₂/kWh) |",
    "|---|---:|---:|",
]
for name, result in card["summary"].items():
    lines.append(f"| {name} | {result['mae']:.2f} | {result['rmse']:.2f} |")
lines += [
    "",
    f"Nominal 90% interval coverage: **{card['summary']['lightgbm']['coverage']:.1%}**.",
    f"Mean interval width: **{card['summary']['lightgbm']['interval_width']:.2f} gCO₂/kWh**.",
    "",
    "| Fold | Test origin start | Last test target | LightGBM MAE | Persistence MAE | Coverage |",
    "|---|---|---|---:|---:|---:|",
]
for f in card["folds"]:
    lines.append(
        f"| {f['fold']} | {f['test_start'][:16]} | {f['test_end'][:16]} | {f['lightgbm']['mae']:.2f} | {f['persistence']['mae']:.2f} | {f['lightgbm']['coverage']:.1%} |"
    )
lines += [
    "",
    "Units are gCO₂/kWh. Times are UTC. Test-origin windows do not overlap, but consecutive issue times have overlapping target horizons; errors are correlated.",
    "The candidate fails the stricter gate: MAE must beat all four baselines and interval coverage must reach the nominal 90%. A passing retrospective gate would still not confer production approval.",
    "No hyperparameter search was performed against these test windows. Future improvements need a new untouched holdout or prospective evaluation.",
]
(output / "RESULTS.md").write_text("\n".join(lines) + "\n")
print(f"Exported {len(predictions)} scored forecasts and {len(sources)} source snapshots")
