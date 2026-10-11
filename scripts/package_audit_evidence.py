"""Export audit evidence from real local outputs; never synthesise source observations."""

import hashlib
import json
import shutil
import tarfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import mlflow
import pandas as pd

from gridflex.cli import read_carbon
from gridflex.features import training_features
from gridflex.monitoring import reference_profile

root = Path(__file__).resolve().parents[1]
out = root / "docs/evidence"
card_path = root / "models/production/model_card.json"
card = json.loads(card_path.read_text())
report = json.loads((out / "scientific-audit.json").read_text())

# Preserve the exact old issue; join only subsequently retrieved labels.
issued = json.loads((out / "live-forecast-2026-09-25.json").read_text())
predictions = pd.DataFrame(issued["slots"])
predictions["timestamp"] = pd.to_datetime(predictions.timestamp, utc=True)
observed = read_carbon(root / "data/processed/carbon.csv")
scored = predictions.merge(observed[["timestamp", "actual"]], on="timestamp", validate="one_to_one")
scored.to_csv(out / "prospective-scored.csv", index=False)
shutil.copy2(root / "data/processed/monitoring.json", out / "monitoring-audit.json")

# Correct the reference distribution's duplicate-origin weighting without refitting.
gold, _ = training_features(read_carbon(root / "data/reference/carbon.csv"))
cal_start = gold.origin.max() - pd.Timedelta(days=14)
fit = gold[gold.origin < cal_start - pd.Timedelta(days=1)].drop_duplicates("origin")
(root / "models/production/reference.json").write_text(
    json.dumps(reference_profile(fit, ["latest", "mean_24h", "std_24h"]), indent=2)
)
card["live_validation"] = "One prospective origin scored; insufficient for performance conclusions"
card["drift_reference_note"] = "Audit uses one sample per fit origin; fitted model weights are unchanged"
card_path.write_text(json.dumps(card, indent=2))
replay_path = root / "models/production/replay.json"
replay = json.loads(replay_path.read_text())
replay["candidate_gate_passed"] = card["candidate_gate_passed"]
replay["audit_note"] = "Gate metadata corrected; historical prediction values unchanged"
replay_path.write_text(json.dumps(replay, indent=2))

snapshots = []
with tarfile.open(out / "raw-source-snapshots.tar.gz", "w:gz") as archive:
    for path in sorted((root / "data/raw").glob("*/*.json")):
        raw = json.loads(path.read_text())
        digest = hashlib.sha256(
            json.dumps(raw["payload"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        assert digest == raw["sha256"] == path.stem
        archive.add(path, arcname=str(path.relative_to(root / "data")))
        snapshots.append(
            {
                "source": path.parent.name,
                "retrieved_at": raw["retrieved_at"],
                "request": raw["request"],
                "payload_sha256": digest,
            }
        )
manifest = {
    "source_snapshots": snapshots,
    "model_sha256": card["model_sha256"],
    "committed_training_csv_sha256": hashlib.sha256(
        (root / "data/reference/carbon.csv").read_bytes()
    ).hexdigest(),
}
(out / "data_manifest.json").write_text(json.dumps(manifest, indent=2))
shutil.copy2(root / "data/processed/quality.json", out / "latest_ingestion_quality.json")
for name in ("dependency-audit.json", "dev-dependency-audit.json", "npm-audit.json"):
    shutil.copy2(root / "artifacts" / name, out / name)

# Record a separate diagnostic run, rather than altering the original training run.
mlflow.set_tracking_uri(f"sqlite:///{root / 'mlflow.db'}")
mlflow.set_experiment("uk-grid-flexibility")
with mlflow.start_run(run_name="strict-audit-diagnostics"):
    mlflow.set_tags({"model_sha256": card["model_sha256"], "scope": "post-build diagnostics; no refit"})
    mlflow.log_params({"coverage_gate": 0.9, "baseline_count": 4, "model_refitted": False})
    for name, values in report["summary"].items():
        mlflow.log_metrics({f"{name}_{key}": value for key, value in values.items()})
    mlflow.log_metric("candidate_gate_passed", int(card["candidate_gate_passed"]))
    mlflow.log_artifact(str(out / "scientific-audit.json"))
runs = mlflow.search_runs(experiment_names=["uk-grid-flexibility"])
columns = [
    c
    for c in runs
    if c.startswith(("metrics.", "params.", "tags.data_", "tags.model_", "tags.scope"))
    or c in ("run_id", "status", "start_time", "end_time")
]
runs[columns].to_json(out / "mlflow_runs.json", orient="records", date_format="iso", indent=2)

tree = ET.parse(out / "python-tests.xml")
for element in tree.iter():
    if "hostname" in element.attrib:
        element.attrib["hostname"] = "local-verification"
tree.write(out / "python-tests.xml", encoding="utf-8", xml_declaration=True)
coverage = json.loads((root / "artifacts/coverage-audit.json").read_text())["totals"]
suite_results = list(tree.iter("testsuite"))
assert sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suite_results) == 0
record = {
    "generated_at": datetime.now(UTC).isoformat(),
    "python_tests": sum(int(s.get("tests", 0)) for s in suite_results),
    "statement_coverage_pct": coverage["percent_covered"],
    "raw_payloads_verified": len(snapshots),
    "model_sha256": hashlib.sha256((root / "models/production/model.txt").read_bytes()).hexdigest(),
    "cloud_deployed": False,
    "docker_executed_locally": False,
    "terraform_provider_validation": "pending external CI; earlier local provider socket unavailable",
}
assert record["model_sha256"] == card["model_sha256"]
(out / "audit-verification.json").write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2))
