# versions.tf
terraform {
  required_version = ">= 1.6.0, < 2.0.0"    # 1.9.x is courant eind 2025

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.115"                  # Dit is de nieuwste stabiele versie op 1 dec 2025
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.53"
    }
  }

  # Backend blijft leeg → wordt tijdens init overschreven met -backend-config=backend.xxx.conf
  backend "azurerm" {}
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false   # veilig voor productie
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}