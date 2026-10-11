resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}
resource "azurerm_resource_group" "app" {
  name     = "${var.name}-rg"
  location = var.location
  tags     = { project = "uk-grid-flexibility", purpose = "portfolio" }
}
resource "azurerm_log_analytics_workspace" "app" {
  name                = "${var.name}-logs"
  location            = var.location
  resource_group_name = azurerm_resource_group.app.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.1
}
resource "azurerm_container_app_environment" "app" {
  name                       = "${var.name}-environment"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.app.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.app.id
}
resource "azurerm_storage_account" "data" {
  name                            = "gridflex${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.app.name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
}
resource "azurerm_storage_share" "data" {
  name               = "gridflex-data"
  storage_account_id = azurerm_storage_account.data.id
  quota              = 5
}
resource "azurerm_container_app_environment_storage" "data" {
  name                         = "gridflex-data"
  container_app_environment_id = azurerm_container_app_environment.app.id
  account_name                 = azurerm_storage_account.data.name
  share_name                   = azurerm_storage_share.data.name
  access_key                   = azurerm_storage_account.data.primary_access_key
  access_mode                  = "ReadWrite"
}
resource "azurerm_container_app" "app" {
  name                         = var.name
  container_app_environment_id = azurerm_container_app_environment.app.id
  resource_group_name          = azurerm_resource_group.app.name
  revision_mode                = "Single"
  registry { server = "ghcr.io" }
  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "auto"
    allow_insecure_connections = false
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
  template {
    min_replicas = 0
    max_replicas = 1
    volume {
      name          = "data"
      storage_type  = "AzureFile"
      storage_name  = azurerm_container_app_environment_storage.data.name
      mount_options = "uid=10001,gid=10001,dir_mode=0700,file_mode=0600"
    }
    container {
      name   = "gridflex"
      image  = var.container_image
      cpu    = 0.5
      memory = "1Gi"
      env {
        name  = "GRIDFLEX_DATA_DIR"
        value = "/app/data"
      }
      volume_mounts {
        name = "data"
        path = "/app/data"
      }
      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"
      }
      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/ready"
      }
      startup_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"
      }
    }
  }
}
resource "azurerm_container_app_job" "maintenance" {
  name                         = "${var.name}-maintenance"
  location                     = var.location
  resource_group_name          = azurerm_resource_group.app.name
  container_app_environment_id = azurerm_container_app_environment.app.id
  replica_timeout_in_seconds   = 900
  replica_retry_limit          = 1
  registry { server = "ghcr.io" }
  schedule_trigger_config {
    cron_expression          = "23 1,7,13,19 * * *"
    parallelism              = 1
    replica_completion_count = 1
  }
  template {
    volume {
      name          = "data"
      storage_type  = "AzureFile"
      storage_name  = azurerm_container_app_environment_storage.data.name
      mount_options = "uid=10001,gid=10001,dir_mode=0700,file_mode=0600"
    }
    container {
      name    = "maintenance"
      image   = var.container_image
      cpu     = 0.5
      memory  = "1Gi"
      command = ["gridflex", "maintenance"]
      env {
        name  = "GRIDFLEX_DATA_DIR"
        value = "/app/data"
      }
      volume_mounts {
        name = "data"
        path = "/app/data"
      }
    }
  }
}
resource "azurerm_monitor_action_group" "operator" {
  count               = var.alert_email == "" ? 0 : 1
  name                = "${var.name}-operator"
  resource_group_name = azurerm_resource_group.app.name
  short_name          = "gridflex"
  email_receiver {
    name          = "operator"
    email_address = var.alert_email
  }
}
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "failures" {
  name                  = "${var.name}-failures"
  resource_group_name   = azurerm_resource_group.app.name
  location              = var.location
  evaluation_frequency  = "PT5M"
  window_duration       = "PT5M"
  scopes                = [azurerm_log_analytics_workspace.app.id]
  severity              = 2
  skip_query_validation = true
  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where ContainerAppName_s startswith "${var.name}"
      | where Log_s has "live_forecast_failed" or Log_s contains '"status": "alert"' or Log_s has "Traceback"
      | summarize ErrorCount = count() by bin(TimeGenerated, 5m)
    KQL
    time_aggregation_method = "Total"
    metric_measure_column   = "ErrorCount"
    operator                = "GreaterThan"
    threshold               = 0
    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }
  dynamic "action" {
    for_each = var.alert_email == "" ? [] : [1]
    content { action_groups = [azurerm_monitor_action_group.operator[0].id] }
  }
}
