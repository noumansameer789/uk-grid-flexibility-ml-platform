# GridFlex completion record

## 24 November 2026 UTC

Nouman Sameer owns the Azure for Students subscription and approved the saved plan, the subscription budget and the GitHub connection. Claude (Anthropic, Fable 5.2) ran the session in Azure Cloud Shell through the owner's browser and wrote the changes below. The starting commit was `da3e1f3524b9c62ceb3e85e936ea3c19d95eea15`. This section supersedes the publication and Azure rows of the 23 November table.

| Work | Observation | Evidence |
|---|---|---|
| Container publication | Publisher runs 45320148701 and 45320239601 succeeded on `main`. The package is public. Run 45320714585 pulled the release without credentials. The Azure preflight received 200 for the pinned digest's manifest using an anonymous token. | [Publisher run](https://github.com/noumansameer789/uk-grid-flexibility-ml-platform/actions/runs/45320239601) · [Anonymous pull](https://github.com/noumansameer789/uk-grid-flexibility-ml-platform/actions/runs/45320714585) · [Preflight](evidence/azure-deployment-2026-11-24/preflight.txt) |
| Azure preflight | The subscription was Azure for Students. Its region policy excluded `uksouth`, so the run used Germany West Central. The four providers registered. A budget of 5 per month was created with alerts at 50% and 100%. | [Preflight](evidence/azure-deployment-2026-11-24/preflight.txt) · [Budget](evidence/azure-deployment-2026-11-24/budget.txt) |
| Terraform | The first apply stopped at the storage link because Azure had created an express environment. The configuration now requests workload-profiles mode through AzAPI and declares the Consumption profile. The third apply completed, and a further plan reported no changes. A single apply from empty is untested. | [Run record](evidence/azure-deployment-2026-11-24/README.md) |
| Azure gates | All ten passed between 21:08 and 21:16 UTC. The strict maintenance job exited 2 on a drift alert, as designed, with its three operational checks `ok`. | [Gate table](evidence/azure-deployment-2026-11-24/README.md#gates) |
| Teardown | `terraform destroy` removed all 11 resources between 21:18 and 21:44 UTC. At 21:45 `az group exists --name gridflex-rg` returned `false`, and the subscription listed no resource group and 0 resources. Azure keeps the deleted Log Analytics workspace recoverable for 14 days. The budget remains. | [Teardown](evidence/azure-deployment-2026-11-24/teardown.txt) · [Destroy output](evidence/azure-deployment-2026-11-24/terraform-destroy.txt) |
| Power BI | No change. Desktop authoring, report read-back, PDF and screenshots remain pending. | [Walkthrough](../powerbi/WALKTHROUGH.md) |

Still untested on Azure: a single apply from empty, alert email delivery, the cron trigger and a scale-from-zero request. Check Cost analysis on 25 November.

## 23 November 2026 UTC

Nouman Sameer supplied the Power BI kit and the release criteria. OpenAI Codex (GPT-6) made the repository changes and reviewed the results below. The starting commit was `36368206a77fca08d868138372e2baadcac58d84`.

| Work | Observation | Evidence |
|---|---|---|
| Baseline CI | All three jobs passed on 2 November. Pytest reported 62 passes and one warning. Coverage counted 1,017 statements and 150 misses, or 85.25% before rounding. | [CI output](evidence/completion-2026-11-23/baseline-ci-23.txt) |
| Scheduled collector | Run 122 exited 2. Carbon freshness and issuance were healthy. Weather ingestion recorded `SourceUnavailable`. Drift was advisory and performance had insufficient data. The underlying weather HTTP cause is unknown. | [Full maintenance JSON and exit status](evidence/completion-2026-11-23/baseline-monitoring-122.txt) |
| Scientific reproduction | The original audit script completed in a separate copy. All values in the four outputs agreed within the recorded tolerances. The largest absolute difference was below 6 × 10⁻¹⁴. | [Execution and comparisons](evidence/completion-2026-11-23/baseline-scientific-audit.txt) |
| Windows checks | Local Ruff checks and five public-demo tests passed. The development packages could not be installed from the local environment. Supplemental pytest results and the unavailable local container and infrastructure checks are recorded separately from GitHub CI. | [Commands and exit statuses](evidence/completion-2026-11-23/baseline-local-checks.txt) |
| Terraform | Commit `1b24024` removed two credentialless registry declarations. Terraform 1.13.3 initialised, formatted and validated the revised configuration in CI. | [Provider evidence](evidence/azure-deployment-2026-11-23/terraform-source.txt) · [Infrastructure job](https://github.com/noumansameer789/uk-grid-flexibility-ml-platform/actions/runs/45283850543/job/138074935114) |
| Dependency repair | PR 16 first failed the Python advisory scan. The clean Linux regeneration produced 30 runtime and 101 development pins. Three development pins changed. Both closures passed their advisory scans and all PR checks passed before merge. | [Initial failure, exact pins and fresh audits](evidence/completion-2026-11-23/dependency-repair.txt) · [PR 16](https://github.com/noumansameer789/uk-grid-flexibility-ml-platform/pull/16) |
| Main CI after PR 16 | Merge commit `69b3730` passed all three jobs. Pytest reported 62 passes. The Python and npm advisories, Docker build, HTTP/UI smoke tests and Terraform validation passed. | [Tests and container on main](https://github.com/noumansameer789/uk-grid-flexibility-ml-platform/actions/runs/45284928303) |
| Container publication | The GitHub publisher displayed zero runs at preflight and the browser requested owner sign-in. The Docker build passed in CI. A published digest, package visibility and an anonymous pull remain unverified. | [Publication preflight and Dockerfile inputs](evidence/completion-2026-11-23/image-publication.txt) · [Existing manual publisher](https://github.com/noumansameer789/uk-grid-flexibility-ml-platform/actions/workflows/publish.yml) |
| Power BI | Rebuilt all three CSVs and checked every numerical acceptance criterion, including the April and fold 3 selections. The supplied `+1.15` DAX comment differs from the computed `1.14`. Desktop authoring, report read-back, PDF and screenshots remain pending. | [Numbers and hashes](evidence/completion-2026-11-23/powerbi-data.txt) · [Desktop preflight](evidence/completion-2026-11-23/powerbi-desktop-preflight.txt) · [Build and read-back](../powerbi/WALKTHROUGH.md) |
| Azure | The local tools and authenticated student subscription were unavailable at preflight. No plan, apply or destroy ran. All ten gates, alert delivery and resource-group absence are unverified. | [Ten gates and raw preflight](evidence/azure-deployment-2026-11-23/README.md) |

## Reproduction decisions

The first Windows rebuild used CRLF. A second run selected LF for that Python process and reproduced the supplied bytes exactly. The generator, DAX expressions and data in the kit retain their supplied contents. The report walkthrough follows the Desktop fallback. It identifies the checks still needed on the saved PBIX.

The runtime and development closure capture used a read-only verification job on a separate Git branch. This provided the Linux environment required by the repository locks. The seven-day mean remains the live demo model. Across-season as-issued performance and commercial evaluation remain open. [Release gates](AUDIT.md) · [Holdout decision](../reports/temporal_holdout/results.json)

## Final review

The [Windows rerun](evidence/completion-2026-11-23/final-local-rerun.txt) used the repaired lock and repeated the scientific audit in a disposable copy. The [repository review](evidence/completion-2026-11-23/final-review.txt) covers published figures, Markdown destinations, protected paths and private data in the proposed changes. The [main workflow history](https://github.com/noumansameer789/uk-grid-flexibility-ml-platform/actions/workflows/ci.yml?query=branch%3Amain) gives the post-merge run for each revision.

The account owner controls system installation, sign-in and package visibility. After a verified anonymous pull, the Azure run still requires the student subscription, its allowed region, credit and budget checks, an exact saved plan, same-session tests and proof of teardown. The build instructions list every Desktop acceptance check and export. [Azure runbook](DEPLOYMENT.md) · [Report walkthrough](../powerbi/WALKTHROUGH.md)
