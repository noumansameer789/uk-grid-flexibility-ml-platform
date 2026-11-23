# Azure preflight, 23 November 2026 UTC

The local shell could run neither `az account show` nor `terraform version`. The session stopped before subscription selection, region-policy inspection, provider registration, budget setup and planning. No Terraform apply or destroy was issued. The resource group's existence is **unverified**. The attempted `az group exists --name gridflex-rg` returned a command lookup error. See the [UTC command output](preflight.txt).

The [configuration comparison](terraform-source.txt) records the two deleted registry declarations, the provider lock's Git blob hash and the matching registry check in AzureRM 4.81.0.

This session obtained no Azure region, applied image digest, revision name, resource inventory or job execution. The table records the missing observations. Each link is the preflight output explaining the block. No endpoint, job, share or alert returned a gate result.

| Gate | Result | Missing observation | Evidence |
|---|---|---|---|
| 1. Health | Not tested | Cold-start response body with status and version | [Preflight](preflight.txt) |
| 2. Readiness | Not tested | Ready response and model SHA-256 to compare with the [model card](../../../models/production/model_card.json) | [Preflight](preflight.txt) |
| 3. Live forecast | Not tested | Live response with 48 slots, or a 503 and the additional replay response | [Preflight](preflight.txt) |
| 4. Charging schedule | Not tested | Plan returned by posting an empty JSON object | [Preflight](preflight.txt) |
| 5. Dashboard in a browser | Not tested | Azure address, live forecast selection, calculated charge and screenshot | [Preflight](preflight.txt) |
| 6. Manual maintenance job | Not tested | Manual execution status and the JSON printed by its strict command | [Preflight](preflight.txt) |
| 7. Shared volume | Not tested | File listing demonstrating writes from both the web app and the job | [Preflight](preflight.txt) |
| 8. Restart persistence | Not tested | File listings across a revision restart and the monitoring response afterwards | [Preflight](preflight.txt) |
| 9. Simultaneous issuance | Not tested | Matching forecast IDs from two concurrent live requests | [Preflight](preflight.txt) |
| 10. Alert rule | Not tested | Enabled state of the rule in Azure. Email delivery also untested | [Preflight](preflight.txt) |

The [deployment guide](../../DEPLOYMENT.md) gives the account, saved plan and teardown checks for a future run. Recheck Cost analysis the day after an actual deployment.
