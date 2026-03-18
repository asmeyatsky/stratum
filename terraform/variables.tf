variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Primary GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "domain" {
  description = "Custom domain for the application (e.g. app.stratum.dev)"
  type        = string
  default     = ""
}

# Database
variable "db_tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-f1-micro"
}

variable "db_ha" {
  description = "Enable Cloud SQL high availability"
  type        = bool
  default     = false
}

# Cloud Run
variable "api_cpu" {
  description = "Cloud Run CPU allocation (e.g. 1, 2)"
  type        = string
  default     = "1"
}

variable "api_memory" {
  description = "Cloud Run memory allocation"
  type        = string
  default     = "512Mi"
}

variable "api_min_instances" {
  description = "Cloud Run minimum instances (0 = scale to zero)"
  type        = number
  default     = 0
}

variable "api_max_instances" {
  description = "Cloud Run maximum instances"
  type        = number
  default     = 10
}

variable "api_image" {
  description = "Container image for the API (full path including tag)"
  type        = string
  default     = "" # Populated by CI/CD
}
