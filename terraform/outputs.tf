output "api_url" {
  description = "Cloud Run API service URL"
  value       = module.cloud_run.service_url
}

output "frontend_url" {
  description = "Frontend CDN URL"
  value       = module.frontend.cdn_url
}

output "artifact_registry_url" {
  description = "Docker registry URL for pushing images"
  value       = module.artifact_registry.repository_url
}

output "db_connection_name" {
  description = "Cloud SQL connection name for Cloud SQL Auth Proxy"
  value       = module.database.connection_name
}

output "api_service_account" {
  description = "Service account email used by the API"
  value       = module.iam.api_service_account_email
}
