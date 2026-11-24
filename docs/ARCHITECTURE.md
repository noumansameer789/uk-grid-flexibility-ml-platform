# Architecture and data lineage

## Data contracts

All storage and API timestamps are timezone-aware UTC. The UI formats times in `Europe/London`; daylight saving changes never add or remove UTC forecast slots.

| Layer | Files/tables | Contract |
|---|---|---|
| Raw | `data/raw/<source>/<sha256>.json` | Original JSON, retrieval time, request parameters, content hash |
| Silver | `data/gridflex.duckdb`, `silver_grid`, `silver_context` | One carbon interval per start; actual may be null; forecasts required; all values validated |
| Export | `data/processed/carbon.csv`, `context.csv`, `quality.json` | Portable, ordered data and completeness report |
| Gold | `<training-output>/features.csv` | Issue-time features plus separately joined future labels |
| Model | `model.txt`, `model_card.json`, `reference.json` | Native LightGBM text, fingerprint, temporal ranges, intervals and drift reference |
| Issued | `data/issued/<origin>_<model-hash>.json` | Immutable canonical live forecast for display and delayed scoring |

NESO carbon intervals must start on a half hour and last exactly 30 minutes. Values must be finite and nonnegative; missing actuals remain missing. Revisions replace older actuals even when revised downward. A missing revision does not erase a known value. Fourteen-day retrieval windows are deduplicated and filtered to the requested half-open range.

Open-Meteo units are validated explicitly. Three locations are averaged only when all are present at an hour; the context index is repeated to the second half-hour. It is an unweighted weather context index, not a capacity-weighted representation of GB generation. Weather is not a predictor in this model version.

## Forecast design

Every forecast origin generates 48 rows for the next 24 hours. A single boosted-tree model learns direct predictions using the horizon, target-time calendar and fixed historical features. It does not recursively feed its predictions back into the feature set.

The latest eligible carbon interval ends at least two hours before the origin. A 24-hour history window and required day/week lag values must be available. Weekly target lags are always in the eligible past. Source forecasts are kept for context but are excluded from model features because their original historical issuance is not known.

Evaluation uses origins every six hours. Each of three folds has an expanding training set, a separate calibration block and a 14-day test-origin block. Full target windows are purged between partitions. A finite-sample residual quantile determines interval radius. The final model also leaves its calibration block out of fitting; it is not refit on calibration labels after estimating uncertainty.

## Scheduling design

Grid energy needed is `(target SOC - initial SOC) × capacity / efficiency`. Each slot accepts at most `power × 0.5h`. The selected linear objective orders slots, and energy is allocated to the cheapest score until the exact requirement is met. For these divisible, charge-only assumptions, this is the continuous-knapsack optimum. The tests compare the balanced objective with SciPy's independent linear-programming solver.

Balanced scores are a weighted sum of within-horizon min/max-normalised carbon and tariff values. Constant vectors contribute zero. This gives a transparent relative trade-off; it is not a monetary social cost of carbon. Negative tariffs do not permit charging beyond the target.

## Runtime and deployment

One FastAPI process serves both static dashboard assets and APIs. HTTP handlers call synchronous network/ML work in FastAPI's thread pool. Shared cache access is locked. Live forecasts are cached for ten minutes, but the next half-hour origin invalidates the cache. Weather is cached for one hour. Failure does not fall back to falsely labelled live data.

The Terraform configuration allows zero or one web replica. It assigns DuckDB writes to the scheduled job and mounts the same Azure Files share for both processes using the image user's UID/GID. The web process writes issued JSON snapshots. Terraform requires a GHCR image digest. The 24 November Azure run passed its permission, locking and restart-persistence gates on a student subscription. The environment must be in workload-profiles mode, because Azure's default express mode supports neither the share nor the job. [Terraform configuration](../infra/terraform/main.tf) · [Azure run record](evidence/azure-deployment-2026-11-24/README.md)

For larger production workloads: use a managed database and object store, partition/lock scheduled jobs, add gateway quotas, collect archived exogenous forecasts, and validate model promotion prospectively. These are not claimed as current capabilities.
