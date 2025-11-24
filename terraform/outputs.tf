output "resource_group" {
  value = azurerm_resource_group.core.name
}

output "vnet_id" {
  value = azurerm_virtual_network.vnet.id
}

output "log_analytics_id" {
  value = azurerm_log_analytics_workspace.law.id
}
