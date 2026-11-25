# Azure run, 24 November 2026 UTC

The Python service was deployed to Azure Container Apps with Terraform, checked against the ten gates, and removed in the same session. All ten gates passed. The run also found that the Terraform on `main` could not deploy in this subscription: Azure created the Container Apps environment in express mode, which supports neither Azure Files storage nor jobs, although the configuration named no mode. The correction is part of this change.

Nouman Sameer owns the subscription and approved the saved plan, the budget and the GitHub connection. Claude (Anthropic) operated Azure Cloud Shell through the owner's browser, wrote [the capture script](run.sh), diagnosed the failure and wrote the Terraform change. Every command's output is in this folder with its UTC time and exit status. The subscription ID, tenant ID, account name, shell user name and one domain verification ID are redacted; see [Redaction](#redaction).

## What ran

| Item | Value |
|---|---|
| Subscription | Azure for Students, ID ending `b7ec` |
| Region | Germany West Central. The student region policy allows `italynorth`, `denmarkeast`, `germanywestcentral`, `spaincentral` and `norwayeast`. It does not allow `uksouth`, the default in `variables.tf`. [Preflight](preflight.txt) |
| Tools | Azure Cloud Shell (Bash), Azure CLI 2.91.0, Terraform 1.17.0. CI uses Terraform 1.13.3. |
| Providers | AzureRM 4.81.0, Random 3.9.1, AzAPI 2.14.0 |
| Image | `ghcr.io/noumansameer789/uk-grid-flexibility-ml-platform@sha256:1f16c9cddcf62b422d8f82fea4e263676cc59398f0c0febb5ec9db2bad18230b`. An anonymous request for its manifest returned 200 before the plan. |
| Revision | `gridflex--boxw0ws`, 0.5 vCPU, 1 GiB, at most one replica. [Inventory](inventory.txt) |
| Budget | `gridflex-safety-net`: 5 per month in the billing currency, alerts at 50% and 100%. It remains on the subscription. [Response](budget.txt) |

## The express-mode failure and its correction

| UTC | Event | Evidence |
|---|---|---|
| 20:06 | Plan from `main` at `da3e1f3`: 10 to add, 0 to change, 0 to destroy. | [Plan 1](terraform-plan-attempt-1.txt) |
| 20:40 | Apply 1 created seven resources. The environment storage link then returned 400 `ExpressEnvironmentResourceNotSupported: 'Storage' resources are not supported on express environments`. | [Apply 1](terraform-apply-attempt-1.txt) |
| 20:46 | API version `2025-10-02-preview` reported `environmentMode: Express`. A PATCH set `environmentMode` to `WorkloadProfiles`. The mode read `Archived`, then `WorkloadProfiles`. The provisioning state returned to `Succeeded` about 19 minutes after the PATCH. | [Mode record](environment-mode.txt) |
| 21:04 | Apply 2 started before that update had finished. The same PATCH from Terraform returned 409 `ManagedEnvironmentOperationInProgress`. | [Plan 2](terraform-plan-attempt-2.txt) · [Apply 2](terraform-apply-attempt-2.txt) |
| 21:07 | Apply 3 added the mode action, storage link, app and job: 4 added, 0 changed, 0 destroyed. | [Plan 3](terraform-plan.txt) · [Apply 3](terraform-apply.txt) |
| 21:10 | A further plan reported no changes. | [Plan after apply](terraform-plan-after-apply.txt) |

Why Azure chose express is unconfirmed. Microsoft's [express FAQ](https://learn.microsoft.com/en-us/azure/container-apps/express-faq) says a template creates a standard environment unless it sets the mode to express, and it does not describe converting an express environment back. The conversion here used a preview API version.

AzureRM 4.81.0 cannot request a mode. The corrected configuration adds the AzAPI provider and one `azapi_resource_action` that sends the PATCH after the environment exists. The storage link waits for it. The environment declares the `Consumption` workload profile, and the app and job name it. The environment's declaration was added after a plan at 21:02 proposed removing the profile (1 to change, in the [run summary](summary.txt)). The two profile names were added after apply 3, when a plan proposed clearing them on the app and the job (2 to change). That plan was read on screen and not saved. The plan at 21:10 was made with all three parts in place.

**Not tested: a single apply of the corrected configuration from an empty subscription.** In this run the environment had already been converted by hand when Terraform's action ran, so the action completed in 3 seconds. If Azure again creates an express environment, a fresh apply must wait for the conversion, which took about 19 minutes here. Whether the action waits that long, and whether its default timeout allows it, is unverified. Apply 3 also created the app and the job before their profile names were in the configuration. The final configuration has been planned against the live resources and has destroyed them, but it has not created them.

## Gates

| Gate | Result | Observation | Evidence |
|---|---|---|---|
| 1. Health | Pass | 200 at 21:08:38 with `{"status":"ok","version":"1.0.0"}` on the first attempt. The replica created by the apply was already running. | [Body](gate-01-health.json) · [Attempts](gate-01-health.attempts.txt) |
| 2. Readiness | Pass | 200, `status: ready`. The model SHA-256 equals the [model card](../../../models/production/model_card.json). | [Body](gate-02-ready.json) |
| 3. Live forecast | Pass | 200, 48 slots, `mode: live`, origin 21:30, issued at 21:08:41. The replay request also returned 48 slots. | [Live](gate-03-live.json) · [Replay](gate-03-replay.json) |
| 4. Charging schedule | Pass | Posting `{}` returned a 48-slot carbon plan on the replay forecast, 29.07% below immediate charging. Posting `{"mode":"live"}` returned 27.43% on the live forecast. Both are estimates from average intensity. | [Replay plan](gate-04-schedule.json) · [Live plan](gate-04-schedule-live.json) |
| 5. Dashboard in a browser | Pass | Chromium 156 in the Claude desktop app on the owner's PC, at the app's own address. Live forecast selected: 48 rows. A plan calculated with the default inputs: 33.3 kWh, 3.21 kgCO2 against 4.42 kgCO2 for immediate charging. The address and values were read from the page. The screenshot shows the page without the address bar and is held by the owner, not in this folder. | [Page record](gate-05-browser.txt) |
| 6. Manual maintenance job | Pass | Execution `gridflex-maintenance-gfheh4h` ran both permitted attempts. Each wrote the report and exited 2, so Azure records `Failed`. The report gives data freshness, forecast issuance and weather ingestion as `ok`, drift as `alert` and performance as `insufficient_data`. This is the strict command's documented behaviour, not a model pass. | [Execution and printed JSON](gate-06-job.txt) · [Saved report](gate-06-monitoring.json) |
| 7. Shared volume | Pass | 17 files. The web app wrote the issued forecast at 21:08:41, before the job started at 21:09:41. The job wrote the DuckDB file, three processed files and the report at 21:10:39 to 21:10:40. | [Listing](gate-07-share.txt) |
| 8. Restart persistence | Pass | Revision restarted at 21:13:28. By 21:15:35 the only replica was a new one created at 21:13:32. It returned the same forecast ID and the original issue time, so the forecast came from the share. The listing held the same 17 files before and after. The monitoring endpoint returned the job's report. | [Restart record](gate-08-restart.txt) · [Before](gate-08-share-before.txt) · [After](gate-08-share-after.txt) |
| 9. Simultaneous issuance | Pass | Two live requests started in the same second. Both returned 200 with the same forecast ID, and the share holds one issued file for that origin. | [Request A](gate-09-live-a.json) · [Request B](gate-09-live-b.json) |
| 10. Alert rule | Pass | `gridflex-failures` exists with `enabled: true`, severity 2 and five-minute evaluation. No action group was configured. | [Rule](gate-10-alert-rule.txt) |

The [run summary](summary.txt) holds one line per step as the script printed it. The line that counts zero inventory resources is a script fault; the typed listing has six.

## Observations

- **Start-up.** The two replica starts took 3.0 and 2.1 seconds from container start to `Application startup complete`. Each logged one failed start-up probe at the moment the container started. The default probe window of 20 to 30 seconds was not approached. [Platform events](log-analytics-system.txt) · [Container output](log-analytics-console.txt)
- **Azure Files.** DuckDB, atomic replacement and the directory lock worked on the SMB share across two job attempts and one restart. That is two writes of the database, not a soak test.
- **Logs.** Log Analytics returned 378 console rows and 51 platform rows within nine minutes of the app starting. The live platform stream command failed on a wrong flag in the script. [Stream output](app-system-logs.txt)

## Not tested

- A single apply of the corrected configuration from empty, as described above. This includes creating the app and the job with their profile names set.
- Alert email delivery. Whether the rule fired on the job's alert lines was not checked.
- A scale-from-zero request through the ingress. The app was already running at every request.
- The cron trigger. The job was started by hand once.

## Teardown

| UTC | Step | Result | Evidence |
|---|---|---|---|
| 21:17 | `terraform plan -destroy` | 0 to add, 0 to change, 11 to destroy. | [Destroy output](terraform-destroy.txt) |
| 21:18 to 21:44 | `terraform destroy` | 11 destroyed, exit status 0. Eight resources were gone within half a minute. The environment took 24 minutes 15 seconds, then the workspace 14 seconds and the resource group 25 seconds. | [Destroy output](terraform-destroy.txt) |
| 21:45 | `az group exists --name gridflex-rg` | `false` | [Teardown checks](teardown.txt) |
| 21:45 | `az group list` and `az resource list` | The subscription held no resource group and 0 resources. | [Teardown checks](teardown.txt) |
| 21:46 | Deleted workspaces | Azure listed `gridflex-logs` as a deleted workspace that can still be recovered. | [Teardown checks](teardown.txt) |
| 21:46 | Budgets | `gridflex-safety-net` was still present, as intended. | [Teardown checks](teardown.txt) |

The resources existed from 20:40 to 21:44 UTC. Cost analysis had not been checked when this record was written.

Azure keeps the name and data of a deleted Log Analytics workspace for 14 days. Creating a workspace with the same name in the same subscription, resource group and region during that time recovers the old one. It was left to expire. Removing it sooner needs a recovery followed by a delete with the force flag. See Microsoft's [workspace delete reference](https://learn.microsoft.com/rest/api/loganalytics/workspaces/delete).

The Terraform state, saved plan, variables file and provider directory were deleted from the Cloud Shell clone after the checks. The Cloud Shell session had no persistent storage.

## Redaction

The script replaces the subscription ID, tenant ID, account name and shell user name as it writes each file. Its `scan` step searches the folder for those values, storage keys, tokens and email addresses. After the last change to the evidence, the scan matched one file, `run.sh`, which contains the search patterns themselves. Two values got past the script and were replaced by hand:

- Terraform shortens resource IDs in its `Still destroying` lines. 148 lines of the destroy output held the first part of the subscription ID.
- The destroy plan printed the environment's custom domain verification ID. It is an identifier, not a credential.

The Log Analytics workspace ID in the query commands belongs to the deleted workspace and is left in place.
