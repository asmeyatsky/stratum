variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "network_id" {
  type = string
}

variable "tier" {
  type    = string
  default = "db-f1-micro"
}

variable "ha_enabled" {
  type    = bool
  default = false
}

variable "db_password_secret" {
  type        = string
  description = "Secret Manager secret ID for the database password"
}

variable "labels" {
  type    = map(string)
  default = {}
}
