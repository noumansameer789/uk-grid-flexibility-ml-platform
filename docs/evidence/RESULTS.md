# Measured backtest

Generated from the saved model card; all values use real NESO observations.

| Model | MAE (gCO₂/kWh) | RMSE (gCO₂/kWh) |
|---|---:|---:|
| lightgbm | 36.61 | 45.49 |
| persistence | 42.48 | 54.03 |
| weekly_seasonal | 47.51 | 58.87 |
| daily_seasonal | 41.14 | 51.92 |
| seven_day_mean | **35.46** | **43.28** |

Nominal 90% interval coverage: **86.3%**.
Mean interval width: **141.65 gCO₂/kWh**.

| Fold | Test origin start | Last test target | LightGBM MAE | Persistence MAE | Coverage |
|---|---|---|---:|---:|---:|
| 1 | 2026-08-09T00:00 | 2026-08-23T17:30 | 30.64 | 49.30 | 78.1% |
| 2 | 2026-08-23T00:00 | 2026-09-06T17:30 | 28.10 | 37.81 | 99.6% |
| 3 | 2026-09-06T00:00 | 2026-09-20T17:30 | 51.08 | 40.32 | 81.1% |

Units are gCO₂/kWh. Times are UTC. Test-origin windows do not overlap, but consecutive issue times have overlapping target horizons; errors are correlated.
The candidate fails the stricter gate: MAE must beat all four baselines and interval coverage must reach the nominal 90%. A passing retrospective gate would still not confer production approval.
No hyperparameter search was performed against these test windows. Future improvements need a new untouched holdout or prospective evaluation.

The 30 September audit added daily/weekly-mean baselines, horizon metrics, a paired moving-block bootstrap and charging-outcome diagnostics without changing model weights. See `scientific-audit.json`, `extended-backtest.csv.gz` and `charging-evaluation.csv` for reproducible detail. The seven-day mean has better point accuracy; LightGBM's default charging simulation has a slightly lower mean observed carbon proxy (2.619 versus 2.665 kg). The latter is a simulated descriptive comparison over correlated scenarios, not evidence of commercial benefit or causal emissions savings.
