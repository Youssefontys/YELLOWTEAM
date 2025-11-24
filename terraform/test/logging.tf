# Logging & monitoring for TEST
# NSG logs to Log Analytics
resource "azurerm_monitor_diagnostic_setting" "diag_nsg_app" {
  name                       = "${var.prefix}-diag-nsg-app"
  target_resource_id         = azurerm_network_security_group.nsg_app.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id

  log {
    category = "NetworkSecurityGroupEvent"
    enabled  = true
  }

  log {
    category = "NetworkSecurityGroupRuleCounter"
    enabled  = true
  }
}

