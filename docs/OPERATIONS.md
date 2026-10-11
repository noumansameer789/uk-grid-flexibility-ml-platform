# Operating the platform

Run `gridflex maintenance` to ingest the latest 30 days of carbon data and current three-location weather context, issue a forecast, then compute drift and delayed-label performance. It exits nonzero on an alert or a source/schema failure, so a scheduled runner can surface a failed execution. It does not retrain or promote a model automatically.

The Azure scheduled job uses persistent Azure Files. The GitHub workflow runs independently and preserves issued forecasts in a best-effort cache plus 30-day downloadable artifacts. GitHub caches can be evicted and schedules can be delayed/disabled; they are not a durable production database. Enable Actions email notifications if you want workflow-failure emails. The Azure deployment has a separate log alert; supplying an operator email enables that notification route.

| Signal | Meaning | Response |
|---|---|---|
| `/health` fails | Process not serving | Inspect container startup/logs and image revision |
| `/ready` fails | Model is not loaded | Check model bundle, hash and mount/configuration |
| Live forecast 503 | Upstream outage, missing history or schema failure | Inspect source and raw payload; keep replay explicitly labelled |
| PSI ≥ 0.25 | Feature distribution differs from training | Check seasonality/data issues before changing model |
| Rolling MAE > 1.5× backtest MAE | Live performance deterioration | Compare baseline and errors by horizon; investigate |
| Interval coverage < 90% | Nominal interval target missed | Review residuals; recalibrate on a new reserved period |
| `insufficient_data` | Too few labelled forecasts/origins | Continue collecting; do not interpret as good performance |

Prometheus `/metrics` exposes request counts and latency by bounded route name. JSON console logs omit request bodies and credentials. Azure log rules watch explicit forecast failures, monitoring alerts and Python tracebacks. A first deployment may need a successful job run before the log tables exist. Alert notification delivery must be verified in the target account.

Persist `data/` and back it up. Only the scheduled process writes DuckDB; avoid manually starting overlapping maintenance jobs against the same database. The API and maintenance process may both record a forecast; the first saved issue-time snapshot is the evaluation record. Deploy one web replica for the supplied storage design.

Saved live forecasts use origin plus model hash in the filename and an integrity fingerprint. Atomic replacement prevents partial JSON/CSV reads; a short directory lock makes the first issue canonical across the web process and job. If a writer crashes and leaves a `.json.lock` directory, verify that no writer is running, preserve the existing evidence, then remove only that abandoned lock. Lock contention/corruption fails closed. Filesystem atomicity, shared-volume permissions and DuckDB locking must be verified in Azure before claiming operational readiness; they have only been exercised locally.

The API limits `/api/` requests to 120 per minute per process, request bodies to 16 KiB and body reception to five seconds. It caches upstream failures for 30 seconds. Health checks are exempt. These controls are a portfolio service guardrail, not a distributed abuse-prevention gateway. A 409 means the displayed forecast expired; refresh before replanning. A stale monitoring status means the scheduler needs investigation.

To review a new model, train to a new output folder; compare metrics and full prediction files; run the tests; inspect interval coverage; collect prospective validation; then update the configured bundle/image. Preserve the previous immutable image and model card for rollback. No automatic promotion is implemented.
