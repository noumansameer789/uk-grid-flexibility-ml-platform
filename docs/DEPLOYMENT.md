# Azure deployment

The infrastructure is for an Azure subscription owned or authorised by the operator. No cloud resources have been created by this repository's local setup. Deployment needs a subscription, billing authority and an authenticated Azure session. The project can run fully on a local computer without Azure.

## 1. Publish the container

Run the repository's **Publish container image** workflow. It builds a non-root image and pushes `ghcr.io/<owner>/<repo>:<commit-sha>`. GitHub packages may initially be private: make this project image public in the package settings before using anonymous Azure pulls. The source repository being public does not by itself prove the container package is public.

Publication now depends on the reusable test/container/infrastructure workflow. Use the returned `ghcr.io/<owner>/<repo>@sha256:<64-character-digest>` from its run summary. Commit tags remain mutable; Terraform and the deployment workflow accept only a content digest. Third-party actions are pinned to verified commit SHAs and Dependabot proposes updates.

## 2. Plan the infrastructure

Install Azure CLI and Terraform (tested configuration uses Terraform 1.13.3). Authenticate to your subscription:

```bash
az login
az account set --subscription YOUR_SUBSCRIPTION_ID
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit subscription_id and container_image.
terraform init
terraform plan -out=deployment.tfplan
```

Review the plan and billing before applying. It creates a resource group, Container Apps environment, one web app, one scheduled job, a small Azure Files share, Log Analytics and a log alert. An email action group is created only if `alert_email` is supplied.

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

Azure Files mounts specify UID/GID 10001 with owner-only file/directory modes for the non-root container. Verify write/read persistence from both the web app and job, a restart, simultaneous forecast issuance, and an intentional alert. Provider validation and these mounted-filesystem checks are release gates, not completed evidence. Relevant provider schema: [Container App volumes](https://github.com/hashicorp/terraform-provider-azurerm/blob/v4.81.0/website/docs/r/container_app.html.markdown) and [job volumes](https://github.com/hashicorp/terraform-provider-azurerm/blob/v4.81.0/website/docs/r/container_app_job.html.markdown).

## 4. Continuous deployment

The optional `azure.yml` workflow updates an existing Terraform-created app and job. Configure GitHub's `production` environment and these variables:

`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_APP_NAME`, `AZURE_JOB_NAME`.

Create an Azure workload identity federation for that exact repository/environment. Grant only the resource-group permissions needed to update the app/job. The workflow requests a short-lived OIDC token; it does not require a long-lived Azure client secret. Run it manually with the published immutable image reference. Keep `container_image` in Terraform consistent with the image deployed by the workflow to avoid an accidental rollback at the next apply.

## Cost controls and teardown

The web app has minimum zero and maximum one replica; a cold start is expected. The scheduled job runs four times per day. Log retention is 30 days, with a 0.1 GiB daily ingestion cap; this cap may delay and is not a spending guarantee. Azure Files, log alerts, job runtime and other resources can still incur charges. Free allowances are shared and eligibility/usage vary. Review current Azure prices and configure a subscription budget before activation.

Export any data you need, then review `terraform plan -destroy` and run `terraform destroy` to remove the managed resources. Destroying the storage account removes stored data; retain an external copy first.

Official references: [Container Apps pricing](https://azure.microsoft.com/pricing/details/container-apps/), [GitHub Actions deployment](https://learn.microsoft.com/azure/container-apps/github-actions), [Terraform AzureRM provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs).
