output "dashboard_url" { value = "https://${azurerm_container_app.app.latest_revision_fqdn}" }
output "resource_group" { value = azurerm_resource_group.app.name }
output "app_name" { value = azurerm_container_app.app.name }
output "job_name" { value = azurerm_container_app_job.maintenance.name }
