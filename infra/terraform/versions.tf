terraform {
  required_version = ">= 1.9, < 2.0"
  required_providers {
    azapi   = { source = "Azure/azapi", version = "~> 2.13" }
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.81" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}
provider "azapi" {
  subscription_id = var.subscription_id
}
