// Create hub
module "hub" {
  source         = "./modules/hub"
  prefix         = var.prefix
  resource_group = azurerm_resource_group.hub.name
  location       = var.location
  vnet_range     = "10.0.0.0/24"
}

// Create shared services
module "shared_services" {
  source         = "./modules/shared_services"
  prefix         = var.prefix
  resource_group = azurerm_resource_group.shared.name
  location       = var.location
  vnet_range     = "10.0.1.0/24"
  hub_vnet_id    = module.hub.hub_vnet_id
  fw_ip          = module.hub.fw_ip
}

// Create LLM solution
module "llm_solution" {
  source         = "./modules/llm_solution"
  prefix         = var.prefix
  resource_group = azurerm_resource_group.llm.name
  location       = var.location
  vnet_range     = "10.0.2.0/24"
  hub_vnet_id    = module.hub.hub_vnet_id
  fw_ip          = module.hub.fw_ip
}
