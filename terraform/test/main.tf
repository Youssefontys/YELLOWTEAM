# Terraform main configuration for TEST
# Azure Connection Configuration
terraform {
  required_version = ">= 1.9.0"  #kloppen deze versies nog?

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true #wat doet dit? 
    }
  }
}

# Infrastructure (IaC)
# Define your resources here (App Service, Front Door)
resource "azurerm_resource_group" "main" {
  name     = "rg-cybercon-youssef" #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  location = "westeurope" #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
}

resource "azurerm_cdn_frontdoor_profile" "main" {
  name                = "fd-cybercon-youssef" #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Premium_AzureFrontDoor" #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
}

resource "azurerm_cdn_frontdoor_firewall_policy" "waf" {
  name                = "waf-cybercon-youssef"
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Premium_AzureFrontDoor"
  enabled             = true
  mode                = "Prevention"

  managed_rule {
    type    = "DefaultRuleSet"
    version = "2.1"
  }
  managed_rule {
    type    = "MicrosoftBotManagerRuleSet"
    version = "1.1"
  }

  custom_rule {
    name     = "BlockAdminPaths"
    priority = 1
    type     = "MatchRule"
    action   = "Block"
    match_condition {
      match_variable = "RequestUri"
      operator       = "Contains"
      match_values   = ["/admin", "/.env", "/wp-admin", "/phpmyadmin"]
    }
  }

  custom_rule {
    name                           = "RateLimit"
    priority                       = 2
    type                           = "RateLimitRule"
    action                         = "Block"
    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 300
  }
}

// 

# Resource Group (core)
resource "azurerm_resource_group" "core" {
  name     = "${var.prefix}-rg"
  location = var.location
  tags     = var.tags
}

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "law" {
  name                = "${var.prefix}-law"
  location            = var.location
  resource_group_name = azurerm_resource_group.core.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}


#outpts.tf?
output "resource_group" {
  value = azurerm_resource_group.core.name
}

output "vnet_id" {
  value = azurerm_virtual_network.vnet.id
}

output "log_analytics_id" {
  value = azurerm_log_analytics_workspace.law.id
}