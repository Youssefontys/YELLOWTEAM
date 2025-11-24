# Network Security Group for App
resource "azurerm_network_security_group" "nsg_app" {
  name                = "${var.prefix}-nsg-app"
  location            = var.location
  resource_group_name = azurerm_resource_group.core.name
  tags                = var.tags
}

resource "azurerm_subnet_network_security_group_association" "assoc_app" {
  subnet_id                 = azurerm_subnet.subnet_app.id
  network_security_group_id = azurerm_network_security_group.nsg_app.id
}

# Standard deny-inbound baseline
resource "azurerm_network_security_rule" "deny_inbound" {
  name                        = "deny-inbound"
  priority                    = 4096
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "*"
  destination_address_prefix  = "*"
  network_security_group_name = azurerm_network_security_group.nsg_app.name
  resource_group_name         = azurerm_resource_group.core.name
}
