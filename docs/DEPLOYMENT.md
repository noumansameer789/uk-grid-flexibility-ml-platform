# Azure deployment

The Terraform configuration targets an operator-authorised Azure subscription. It was applied in Azure for Students on 24 November 2026, checked against ten gates and destroyed in the same session. The [run record](evidence/azure-deployment-2026-11-24/README.md) gives the results, the express-mode correction and what remains untested. The [23 November preflight](evidence/azure-deployment-2026-11-23/README.md) is the earlier record.

## 1. Publish the container

Run the repository's **Publish container image** workflow. It builds a non-root image and pushes `ghcr.io/<owner>/<repo>:<commit-sha>`. GitHub packages may initially be private: make this project image public in the package settings before using anonymous Azure pulls. The source repository being public does not by itself prove the container package is public.

Publication now depends on the reusable test/container/infrastructure workflow. Use the returned `ghcr.io/<owner>/<repo>@sha256:<64-character-digest>` from its run summary. Commit tags remain mutable; Terraform and the deployment workflow accept only a content digest. Third-party actions are pinned to verified commit SHAs and Dependabot proposes updates.

Review the project's [Dockerfile](../Dockerfile) before making the package public. Its project inputs are the runtime lock, package metadata, `src/` and four named production model files. The package owner controls visibility. Pull the exact digest from a client without registry credentials and retain the successful pull output before planning the Azure run.

The app and maintenance job use a public image without a `registry` block. AzureRM 4.81.0 checks every supplied block when expanding the resource. A server alone supplies neither an identity nor a username and password secret, so the provider rejects it. See the [pinned registry validator](https://github.com/hashicorp/terraform-provider-azurerm/blob/v4.81.0/internal/services/containerapps/helpers/container_apps.go) and [project provider lock](../infra/terraform/.terraform.lock.hcl).

## 2. Plan the infrastructure

Use Azure CLI with Terraform 1.13.3, the version in [CI](../.github/workflows/ci.yml). The 24 November run used Terraform 1.17.0 in Azure Cloud Shell, and its [capture script](evidence/azure-deployment-2026-11-24/run.sh) holds the Bash equivalents of the commands below. In PowerShell, sign in and select the intended subscription. The following checks read the active subscription and its applicable policy assignments.

```powershell
az login
az account show --query name --output tsv
$subscription = az account show --query id --output tsv
az policy assignment list --scope "/subscriptions/$subscription" --filter "atScope()" --query "[?displayName=='Allowed resource deployment regions'].{name:displayName,parameters:parameters}" --output json
az group exists --name gridflex-rg
```

For the student deployment, continue only in **Azure for Students**. Read the allowed locations from the effective region policy. If the filtered list is empty, inspect all applicable assignments and their parameters before choosing a region. On 24 November the policy allowed five regions and excluded `uksouth`, the default `location`. Container Apps was offered in four of the five. Confirm that `gridflex-rg` is available to create. Check the remaining credit and configure a small subscription budget before activation. If the account reports that budgets are unsupported, record that response. See Microsoft's [policy assignment commands](https://learn.microsoft.com/en-us/cli/azure/policy/assignment) and [student cost guidance](https://learn.microsoft.com/en-us/azure/education-hub/navigate-costs).

Register the four providers used by this project in the verified subscription. The pinned AzureRM release's default registration set omits `Microsoft.App`. If Terraform reports a bulk-registration error, capture it and verify these four registrations before considering explicit registration with `resource_provider_registrations = "none"`. See the [provider's registration sets](https://github.com/hashicorp/terraform-provider-azurerm/blob/v4.81.0/internal/resourceproviders/required.go).

```powershell
foreach ($namespace in 'Microsoft.App','Microsoft.OperationalInsights','Microsoft.Storage','Microsoft.Insights') {
    az provider register --namespace $namespace --wait --output none
    if ($LASTEXITCODE -ne 0) { throw "Registration failed for $namespace" }
    az provider show --namespace $namespace --query "{provider:namespace,state:registrationState}" --output json
}
```

On 24 November 2026 Azure created this environment in express mode, although the configuration named no mode. Express supports neither Azure Files storage nor jobs, and AzureRM 4.81.0 cannot request a mode. The configuration therefore sends one PATCH through the AzAPI provider, using API version `2025-10-02-preview` to set `environmentMode` to `WorkloadProfiles` before the storage link is created. That conversion took about 19 minutes. A second write during the conversion returns 409 `ManagedEnvironmentOperationInProgress`. Wait until the environment reports `provisioningState: Succeeded`, then plan and apply again. A single apply from empty is untested. Why Azure chose express is unconfirmed: Microsoft's [express FAQ](https://learn.microsoft.com/en-us/azure/container-apps/express-faq) says a template creates a standard environment unless it sets the mode to express, and it does not describe this conversion. See Microsoft's [express overview](https://learn.microsoft.com/en-us/azure/container-apps/express-overview) and the [run record](evidence/azure-deployment-2026-11-24/README.md).

Keep local state through teardown. An ephemeral Cloud Shell loses files when its session ends and can time out after 20 idle minutes. See the [Cloud Shell FAQ](https://learn.microsoft.com/en-us/azure/cloud-shell/faq-troubleshooting).

```powershell
cd infra/terraform
if (-not (Test-Path terraform.tfvars)) { Copy-Item terraform.tfvars.example terraform.tfvars }
# Set subscription_id, the public image digest and a policy-approved location in terraform.tfvars.
# Leave alert_email empty unless the operator supplies an address.
terraform init -lockfile=readonly
terraform fmt -check
terraform validate
terraform plan -out=deployment.tfplan
terraform show -no-color deployment.tfplan
```

Check each address and operation in the saved plan. With the default project name and no email action group, it must add exactly eleven resources and change or destroy zero. These are the random suffix, resource group, Log Analytics workspace, Container Apps environment, environment-mode action, storage account, file share, environment storage link, app, maintenance job and scheduled-query alert. A supplied `alert_email` adds one action group. Stop if the criteria or region differ. The next command applies the reviewed plan.

```bash
terraform apply deployment.tfplan
terraform output dashboard_url
```

Keep Terraform state private. Azure Files access keys are sensitive state values even though they are never output. For ongoing collaborative deployment, configure an Azure Storage remote backend with restricted access and locking before the first shared apply. Never commit a state file, plan file, credentials or filled `terraform.tfvars`.

## 3. Verify the actual deployment

```bash
curl --fail https://YOUR_APP_FQDN/health
curl --fail https://YOUR_APP_FQDN/ready
curl --fail https://YOUR_APP_FQDN/api/v1/forecast?mode=live
```

Open the dashboard, select Live forecast and calculate a charge. Check the scheduled job execution logs, the shared volume and the monitoring report. An app URL alone does not prove scheduled ingestion or alerts work. Do not claim deployment is complete until these checks pass on the account.

Azure Files mounts specify UID/GID 10001 with owner-only file and directory modes. Collect the actual app and job files, their persistence after a restart, the monitoring response, and the `forecast_id` of each simultaneous request. Start the maintenance job manually once and retain its printed JSON with the Container Apps execution status. The configured strict command exits with code 2 for an active model alert and permits one retry. Inspect the individual operational and model fields in [the operations guide](OPERATIONS.md). Verify the alert rule's enabled state separately from email delivery. See the [app volume schema](https://github.com/hashicorp/terraform-provider-azurerm/blob/v4.81.0/website/docs/r/container_app.html.markdown) and [job volume schema](https://github.com/hashicorp/terraform-provider-azurerm/blob/v4.81.0/website/docs/r/container_app_job.html.markdown).

Keep UTC-stamped, redacted outputs for each gate under a new dated `docs/evidence/azure-deployment-YYYY-MM-DD/` directory. Record the region, immutable image digest, revision, resource inventory and results there. Check response bodies and keep the browser screenshot of the Azure dashboard. For a failed gate, read system and console logs before changing the configuration. Log Analytics can take time to ingest the first console rows. Terraform abbreviates resource IDs in its `Still destroying` lines, so a redaction that matches the whole subscription ID misses them. Search the saved output for the ID's leading characters as well.

## 4. Continuous deployment

The optional `azure.yml` workflow updates an existing Terraform-created app and job. Configure GitHub's `production` environment and these variables:

`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_APP_NAME`, `AZURE_JOB_NAME`.

Create an Azure workload identity federation for that exact repository/environment. Grant only the resource-group permissions needed to update the app/job. The workflow requests a short-lived OIDC token; it does not require a long-lived Azure client secret. Run it manually with the published immutable image reference. Keep `container_image` in Terraform consistent with the image deployed by the workflow to avoid an accidental rollback at the next apply.

## Cost controls and teardown

The web app has minimum zero and maximum one replica; a cold start is expected. The scheduled job runs four times per day. Log retention is 30 days, with a 0.1 GiB daily ingestion cap; this cap may delay and is not a spending guarantee. Azure Files, log alerts, job runtime and other resources can still incur charges. Free allowances are shared and eligibility/usage vary. Review current Azure prices and configure a subscription budget before activation.

Export any data you need. In the same session, review `terraform plan -destroy` and run `terraform destroy` for this deployment. Save the UTC-stamped output of `az group exists --name gridflex-rg`. Teardown is verified when it returns `false` in the verified subscription. If state is lost, use `az group delete --name gridflex-rg --yes` only after the recorded resource list confirms that this run created the group. Remove the local state, its backups, saved plan and `.terraform/` after confirming deletion. Check Cost analysis the following day. On 24 November the destroy took 26 minutes, 24 of them for the Container Apps environment. Azure keeps a deleted Log Analytics workspace recoverable for 14 days, so `az monitor log-analytics workspace list-deleted-workspaces` still lists it, and creating the same workspace name in the same resource group and region during that time recovers it. See Microsoft's [workspace delete reference](https://learn.microsoft.com/rest/api/loganalytics/workspaces/delete).

See [Container Apps pricing](https://azure.microsoft.com/pricing/details/container-apps/), [GitHub Actions deployment](https://learn.microsoft.com/en-us/azure/container-apps/github-actions) and the [Terraform AzureRM provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs).
