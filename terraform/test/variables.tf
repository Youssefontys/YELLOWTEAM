# Terraform variables for TEST
# Variables (e.g., locations, naming conventions)
variable "prefix" {
  description = "Naam-prefix voor alle resources"
  type        = string
}

variable "location" {
  description = "Azure regio"
  type        = string
  default     = "westeurope"
}

variable "tags" {
  description = "Standaardtags"
  type        = map(string)
  default = {
    environment = "prod"
    owner       = "youssef"
    project     = "landingzone"
  }
}
