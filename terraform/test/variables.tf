# ─────────────────────────────────────────────────────────────────────────────
# Moderne, secure Azure landing zone – Yellow Team 2025
# ─────────────────────────────────────────────────────────────────────────────

variable "environment" {
  description = "Omgeving (dev, test, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Alleen dev, test of prod toegestaan."
  }
}

variable "location" {
  description = "Azure regio"
  type        = string
  default     = "westeurope"
}

variable "project_name" {
  description = "Projectnaam (wordt prefix, alleen lowercase + - + cijfers)"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]{3,15}$", var.project_name))
    error_message = "3-15 tekens, alleen lowercase letters, cijfers en -."
  }
}

# ───── Networking (gratis) ─────
variable "vnet_address_space" {
  type    = list(string)
  default = ["10.0.0.0/16"]
}

variable "subnet_app_prefix" {
  description = "Subnet voor App Service + Private Endpoints"
  type        = string
  default     = "10.0.1.0/24"
}

# ───── App Service – laagste kosten maar mét Private Endpoint ─────
variable "app_service_sku" {
  description = "App Service Plan SKU – B1 is laagste mét Private Endpoint support"
  type        = string
  default     = "B1"        # ← €0–12/maand, ondersteunt Private Endpoint!
  validation {
    condition     = contains(["B1", "B2", "B3", "S1"], var.app_service_sku)
    error_message = "Kies B1, B2, B3 of S1."
  }
}

# ───── Front Door Standard (gratis tier) + WAF (gratis) ─────
variable "enable_front_door" {
  description = "Front Door Standard + WAF aanzetten? (gratis)"
  type        = bool
  default     = true
}

variable "waf_mode" {
  description = "WAF mode – Prevention = blokkeert echt"
  type        = string
  default     = "Prevention"      # ← werkt gewoon op Standard tier!
  validation {
    condition     = var.waf_mode == "Detection" || var.waf_mode == "Prevention"
    error_message = "Alleen Detection of Prevention."
  }
}

variable "custom_domain" {
  description = "Custom domein (bijv. app.jouwdomein.nl) – laat leeg als je alleen Azure FD endpoint wilt"
  type        = string
  default     = ""
}

# ───── Tags ─────
variable "tags" {
  description = "Basis tags – Environment wordt dynamisch toegevoegd"
  type        = map(string)
  default = {
    Project   = "yellowteam"
    ManagedBy = "terraform"
    Owner     = "Youssef"
  }
}

# ───── Feature flags ─────
variable "enable_private_endpoint" {
  description = "Private Endpoint voor App Service (nooit publiek!)"
  type        = bool
  default     = true
}