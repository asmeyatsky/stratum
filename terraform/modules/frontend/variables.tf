variable "project_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "domain" {
  type        = string
  default     = ""
  description = "Custom domain for managed SSL certificate. Leave empty to skip HTTPS."
}
