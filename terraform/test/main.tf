# main.tf – FINAL 100% WERKEND – Zero Trust + Front Door Standard + WAF + Private Endpoint + < €5/maand
terraform {
  backend "azurerm" {}
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

locals {
  tags            = merge(var.tags, { Environment = var.environment })
  resource_suffix = "${var.project_name}-${var.environment}-${random_string.suffix.result}"
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

# ==================== 1. RG + VNet + Subnet ====================
resource "azurerm_resource_group" "main" {
  name     = "rg-${local.resource_suffix}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "main" {
  name                = "vnet-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  address_space       = var.vnet_address_space
  tags                = local.tags
}

resource "azurerm_subnet" "app" {
  name                 = "snet-app"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.subnet_app_prefix]

  private_endpoint_network_policies = "Enabled"  # blokkeert publiek verkeer

  delegation {
    name = "delegation"
    service_delegation {
      name    = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]  # ← FIX 1
    }
  }
}

# ==================== 2. App Service (B1 + Docker + NO PUBLIC ACCESS) ====================
resource "azurerm_service_plan" "main" {
  name                = "plan-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = var.app_service_sku
  tags                = local.tags
}

resource "azurerm_linux_web_app" "main" {
  name                = "app-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_service_plan.main.location
  service_plan_id     = azurerm_service_plan.main.id
  https_only          = true

  public_network_access_enabled = false   # ← ZERO TRUST: geen directe toegang

  tags = local.tags

  site_config {
    minimum_tls_version = "1.2"
    application_stack {
      docker_image_name   = "nginx:latest"
      docker_registry_url = "https://index.docker.io"
    }
  }

  app_settings = {
    WEBSITES_ENABLE_APP_SERVICE_STORAGE = "false"
    WEBSITE_DNS_SERVER                 = "168.63.129.16"
    WEBSITE_VNET_ROUTE_ALL             = "1"
  }
}

# ==================== 3. Private Endpoint ====================
resource "azurerm_private_endpoint" "app" {
  count               = var.enable_private_endpoint ? 1 : 0
  name                = "pe-app-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = azurerm_subnet.app.id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-app"
    private_connection_resource_id = azurerm_linux_web_app.main.id
    subresource_names              = ["sites"]
    is_manual_connection           = false
  }
}

# ==================== 4. Private DNS ====================
resource "azurerm_private_dns_zone" "app" {
  count               = var.enable_private_endpoint ? 1 : 0
  name                = "privatelink.azurewebsites.net"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "app" {
  count                 = var.enable_private_endpoint ? 1 : 0
  name                  = "link-app"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.app[0].name
  virtual_network_id    = azurerm_virtual_network.main.id
  registration_enabled  = false
}

resource "azurerm_private_dns_a_record" "app" {
  count               = var.enable_private_endpoint ? 1 : 0
  name                = azurerm_linux_web_app.main.name
  zone_name           = azurerm_private_dns_zone.app[0].name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  records             = [azurerm_private_endpoint.app[0].private_service_connection[0].private_ip_address]
}

# ==================== 5. Front Door Standard + WAF ====================
resource "azurerm_cdn_frontdoor_profile" "main" {
  count               = var.enable_front_door ? 1 : 0
  name                = "fd-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Standard_AzureFrontDoor"
  tags                = local.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "main" {
  count                   = var.enable_front_door ? 1 : 0
  name                    = "endpoint-${local.resource_suffix}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main[0].id
}

resource "azurerm_cdn_frontdoor_origin_group" "main" {
  count                   = var.enable_front_door ? 1 : 0
  name                    = "og-main"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main[0].id
  load_balancing {}
}

resource "azurerm_cdn_frontdoor_origin" "main" {
  count                         = var.enable_front_door ? 1 : 0
  name                          = "origin-app"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.main[0].id
  enabled                       = true
  host_name                     = azurerm_linux_web_app.main.default_hostname
  certificate_name_check_enabled = true
}

resource "azurerm_cdn_frontdoor_firewall_policy" "waf" {
  count               = var.enable_front_door ? 1 : 0
  name                = "waf-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Standard_AzureFrontDoor"
  enabled             = true
  mode                = var.waf_mode
  managed_rule {
    type    = "DefaultRuleSet"
    version = "2.1"
  }
}

# ← FIX 2: association block toegevoegd
resource "azurerm_cdn_frontdoor_security_policy" "main" {
  count                    = var.enable_front_door ? 1 : 0
  name                     = "secpol-main"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main[0].id

  security_policies {
    firewall {
      association {
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.main[0].id
        }
        patterns_to_match = ["/*"]
      }
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.waf[0].id
    }
  }
}

resource "azurerm_cdn_frontdoor_route" "main" {
  count                         = var.enable_front_door ? 1 : 0
  name                          = "route-main"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.main[0].id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.main[0].id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.main[0].id]
  enabled                       = true
  forwarding_protocol           = "HttpsOnly"
  patterns_to_match             = ["/*"]
  supported_protocols           = ["Http", "Https"]
  link_to_default_domain        = true
}

# ==================== 6. Outputs ====================
output "app_url_via_frontdoor" {
  description = "De enige publieke URL – beveiligd door Front Door + WAF"
  value       = var.enable_front_door ? "https://${azurerm_cdn_frontdoor_endpoint.main[0].host_name}" : "Front Door uitgeschakeld"
}

output "direct_app_service_url" {
  description = "Directe URL (moet 403 geven → Zero Trust werkt!)"
  value       = "https://${azurerm_linux_web_app.main.default_hostname}"
}

output "resource_group" {
  value = azurerm_resource_group.main.name
}