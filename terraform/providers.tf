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

