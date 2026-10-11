# Verification record

Original build: **25 September 2026**. Strict audit and re-verification: **30 September 2026**. These are actual local executions, not assertions that GitHub Actions or Azure have run. See [the full assessment](AUDIT.md) and `evidence/audit-verification.json`.

| Check | Result | Evidence |
|---|---|---|
| Python suite | **47 passed; no failures; 84.47% statement coverage** | `evidence/python-tests.xml`; `evidence/audit-verification.json` |
| Ruff checks and formatting | Passed | CI repeats the checks |
| Dashboard integration | Passed against real local HTTP: five baselines, planning, input errors, mode-response race and request invalidation | `scripts/test-ui.mjs`; `demo-snapshot.html` |
| Source ingestion | Real NESO and Open-Meteo requests succeeded | `evidence/data_manifest.json`; compressed raw snapshots |
| Training and experiment tracking | Completed on real data; MLflow SQLite logging succeeded | Model card, scored predictions and MLflow export |
| Live forecast | 48 slots generated with the real model and live source | `evidence/live-forecast-2026-09-25.json` |
| Scheduled command | Ingestion, live issue and monitoring executed; exited 2 on a drift alert | `evidence/monitoring-2026-09-25.json` |
| Audited scheduled command | Fresh carbon/weather ingestion succeeded; new issue failed closed on missing recent actuals; older forecast still scored; exit 2 | `evidence/monitoring-audit.json`; `evidence/prospective-scored.csv` |
| Python dependency advisory scans | No known vulnerabilities reported in pinned runtime and development closures | `evidence/dependency-audit.json`; `evidence/dev-dependency-audit.json` |
| npm advisory scan | Zero reported vulnerabilities | `evidence/npm-audit.json` |
| Terraform formatting and provider installation | Original build passed; audited configuration reviewed against AzureRM 4.81 schema | CI must validate the revised configuration before deployment |
| Terraform provider schema validation | Could not complete locally: this execution environment disallowed the provider's Unix socket | CI infrastructure job must pass before applying |
| Docker build and container smoke test | Not run locally: Docker was unavailable | CI contains the actual build and HTTP/UI checks |
| Azure deployment, alert delivery, public URL | Not activated or verified | Requires an authorised Azure subscription |

The Python suite emitted one upstream Starlette deprecation warning about its HTTP test client. It did not cause a test failure. CLI and live-network paths were exercised manually and are not fully covered by the unit-test coverage figure.

## Findings that remain visible

- Backtest intervals achieved **86.3% coverage**, below the nominal 90% target. The project reports that undercoverage and does not describe the model as production approved.
- The added seven-day mean beats LightGBM on MAE (35.46 versus 36.61). The stricter candidate gate is false. No weights or calibration radius were tuned against this finding.
- The 25 September maintenance run raised PSI **0.26593** for the 24-hour mean feature, above the configured 0.25 alert threshold. This is a distribution-change signal requiring investigation, not proof of model failure. There were no scored prospective forecasts yet at that point.
- One saved live origin now has 48 labels (MAE 15.62, coverage 100%). This is explicitly insufficient prospective evidence. The latest source lacked recent required actuals, so the audited maintenance run reported a new-issue failure rather than returning stale predictions as current.
- Weather is collected and validated as context. It is excluded from the current forecasting model because historical reanalysis is not an as-issued operational forecast.

The live JSON is an archived observation of a successful request on its stated date. It is not a current forecast. The recorded dashboard HTML is a noninteractive snapshot created from actual API responses. The video is a measured-data walkthrough, not footage of a deployed service.

Advisory scans are time-specific and do not prove freedom from vulnerabilities. Python scanning used the supplied fully pinned dependency closures with dependency resolution disabled; package versions are pinned but installation hashes are not yet enforced. The original MLflow training record remains intact; a separate audit diagnostics run records the stronger comparisons.

## Publication and deployment gates

1. Create the public repository `noumansameer789/uk-grid-flexibility-ml-platform` and push the project files.
2. Require the Tests and container workflow to pass, including the real Docker build and Terraform validation. Resolve any failure before deployment.
3. Publish the container image and make its GHCR package public.
4. Follow `DEPLOYMENT.md` using an authorised Azure subscription; review and apply the actual Terraform plan.
5. Verify live API responses, the public dashboard, scheduled job persistence and alert delivery in that account. Then update the README with the verified public URL.

Do not claim these gates have completed merely because their configuration is included.
