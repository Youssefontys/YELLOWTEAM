# Virtual Network (core)
resource "azurerm_virtual_network" "vnet" {
  name                = "${var.prefix}-vnet"
  address_space       = ["10.10.0.0/16"]
  location            = var.location
  resource_group_name = azurerm_resource_group.core.name
  tags                = var.tags
}

# Subnet App
resource "azurerm_subnet" "subnet_app" {
  name                 = "${var.prefix}-snet-app"
  resource_group_name  = azurerm_resource_group.core.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.10.10.0/24"]
}

# Subnet Management
resource "azurerm_subnet" "subnet_mgmt" {
  name                 = "${var.prefix}-snet-mgmt"
  resource_group_name  = azurerm_resource_group.core.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.10.20.0/24"]
}
