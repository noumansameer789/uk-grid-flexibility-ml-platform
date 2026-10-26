# Strict project assessment — 30 September 2026

This is an evidence-based self-audit carried out with AI assistance against statistical, ML engineering, software engineering and energy-domain criteria. It is not an independent review.

## Verdict

**A defensible research portfolio with a working local service; not a production-approved forecasting product.** Its strongest evidence is reproducible data handling, controlled time-series evaluation, constrained optimisation, explicit failure states and honest negative findings. Publication and container execution are now verified in GitHub Actions; cloud operation remains an unverified release gate.

The most important correction is scientific: LightGBM's MAE is 36.61 gCO₂/kWh, while a seven-day UTC clock-time mean achieves 35.46. Nominal 90% intervals cover 86.27%. The candidate therefore fails both promotion conditions. The previous permissive coverage rule and limited baseline set concealed that conclusion; they have been replaced throughout the code, dashboard and documentation. The fitted weights and calibration radius were not changed to improve the released test scores.

## Findings and resolution

| Review perspective / finding | Resolution | Evidence / remaining boundary |
|---|---|---|
| Assessor: weak baselines and permissive 80% coverage gate | Added daily and seven-day mean baselines to training and audit; gate requires beating every baseline and nominal 90% coverage | `scientific-audit.json`, model card, candidate-gate regression test; gate correctly fails |
| Statistician: aggregate accuracy hid horizon weaknesses and dependent errors | Added four horizon bands and paired seven-day moving-block bootstrap | MAE difference versus best baseline +1.14; exploratory interval −6.77 to +7.50; limited seasonal span |
| Energy reviewer: forecast accuracy did not establish useful scheduling | Added observed-intensity scoring, equal-energy immediate comparator, perfect-information comparator and seasonal-baseline schedules | 168 overlapping scenarios; simulation, not physical savings |
| Data engineer: incomplete API ranges could pass silently | Enforced half-hour request boundaries and complete requested timestamp coverage | Partial-response regression; null actuals remain valid source data, but inference requires eligible history |
| Data engineer: training CSV accepted ambiguous timestamps/sentinels | Reject naive timestamps, misaligned intervals, nonfinite and out-of-range actuals | CSV/schema regression tests |
| Data engineer: local timezone could leak into exported data | Set DuckDB session timezone explicitly to UTC | Source values retain their instants; exports normalised |
| ML engineer: displayed forecast could differ from the one scored | Immutable first-writer canonical JSON, model-specific filenames, atomic writes, fingerprints and restart reuse | Concurrent-writer, restart and corruption regressions |
| ML engineer: an existing fitted bundle could be overwritten casually | Training defaults to a new candidate folder and refuses an existing model | Overwrite regression; no automatic promotion |
| Reliability engineer: source failure skipped delayed scoring | Maintenance records issuance failure and still scores older forecasts | Maintenance failure-path regression and actual 30 September alert report |
| Reliability engineer: repeated upstream failure wasted calls | Added negative cache/cooldown; no silent replay fallback | Failure/cooldown regression |
| Monitoring reviewer: 48 correlated rows looked sufficient | Require distinct origins and target days, deduplicate issues, compare stored baselines, label old reports stale | One observed prospective origin remains insufficient evidence |
| Frontend reviewer: late mode responses overwrote current selection | Request versions discard obsolete responses; loading clears old charts and disables planning/export | Real-HTTP DOM integration race test |
| Frontend reviewer: edited/failed requests left an old plan visible | Form edits invalidate plans; delayed responses cannot restore them | Edited-request and infeasible-plan regressions |
| API reviewer: plan/download could use a different forecast | Optional expected fingerprint returns 409 on mismatch; dashboard always supplies it | API binding regression |
| Security reviewer: request size/time/rate unbounded | Body, receive-time and per-process API limits; liveness exempt | Limits regression; gateway still needed for multi-tenant deployment |
| Platform reviewer: mutable actions/images and ungated publication | Commit-pinned actions, Dependabot, CI prerequisite, digest-only Azure configuration | Workflow/config review; GitHub Actions now runs on every push |
| Platform reviewer: non-root shared-volume access unspecified | Azure mount UID/GID and owner-only modes supplied | Official provider schema checked; cloud mount/locking test still required |
| Reader: claims must match what is demonstrated | Documented the model failure, simulation labels, AI assistance and deployment status | README, model card, this assessment; no invented client, employment or savings claims |

## Scientific and business evidence

The reference set has 9,792 real half-hours, March–September 2026; three 14-day test-origin windows yield 8,064 forecast rows and 168 origins. Horizons overlap. They must not be described as 8,064 independent experiments. Historical actuals may have been revised after their original publication. The added comparisons are post-build diagnostics, not a preregistered study.

For the fixed default battery (60 kWh, 30→80% SOC, 7 kW, 90% efficiency), mean observed-intensity-weighted charging proxy is 2.619 kg for LightGBM schedules, 2.665 kg for seven-day-mean schedules and 3.782 kg for immediate charging. Aggregate reduction versus immediate is 30.75%; 88.10% of scenarios improve. Average regret versus perfect foresight is 0.289 kg. This supports an inspectable scheduling experiment, not guaranteed benefits or a causal carbon-savings claim. No physical charger, customer tariff feed or commercial deployment was used.

The saved 25 September live origin now has 48 realised labels: MAE 15.62 versus 18.60 for the stored NESO forecast, with 100% interval coverage. This is **one origin**, not an established out-of-sample track record. On 30 September, missing recent source actuals prevented a new issue. The pipeline reported an alert and preserved historical scoring. It did not change the lag policy or fabricate missing measurements.

## What the project demonstrates

- Python/FastAPI, SQL/DuckDB data handling, real public-source ingestion and validation.
- Time-series evaluation, leakage controls, baseline selection, uncertainty diagnostics and measured judgement about when not to promote ML.
- Constrained EV/battery scheduling linked to the author's electrical-engineering background.
- Tests, observability and deployment configuration, with cloud execution clearly pending.

Scope: this is an AI-assisted independent portfolio build. It has no commercial deployment, client or realised savings. The Azure/Terraform files are deployment configuration; no Azure deployment has been run. The 30.75% reduction is a simulation result, not a realised emissions saving.

## Remaining release gates

1. Done: the repository is public, and GitHub Actions runs the Python tests, the Docker build with HTTP and dashboard smoke tests, and Terraform validation on every push to `main`.
2. Use an authorised Azure subscription to test shared-volume writes, restart persistence, scheduler execution, real alert delivery and the public URL. No cloud spend has been incurred here.
3. Collect enough as-issued forecasts across seasons. The minimum monitoring count is an operational threshold, not statistical proof. Preserve an untouched future evaluation period for any improved candidate.
4. If pursuing commercial value, agree a real stakeholder objective and evaluate actual operational outcomes.

Run verification details are in `VERIFICATION.md`. Reproduce the added science with `python scripts/audit_evidence.py`; this reuses the committed out-of-fold predictions and reference observations, without refitting the model.
