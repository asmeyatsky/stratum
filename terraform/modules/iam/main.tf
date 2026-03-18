# Service account for Cloud Run API
resource "google_service_account" "api" {
  account_id   = "${var.name_prefix}-api"
  display_name = "Stratum API (${var.name_prefix})"
  project      = var.project_id
}

# Allow Cloud Run to use this service account
resource "google_project_iam_member" "api_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Cloud SQL client — connect via Cloud SQL Auth Proxy sidecar
resource "google_project_iam_member" "api_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Secret accessor — read secrets at runtime
resource "google_project_iam_member" "api_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Cloud Storage — write PDF reports to GCS
resource "google_project_iam_member" "api_storage_writer" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Logging
resource "google_project_iam_member" "api_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Metrics
resource "google_project_iam_member" "api_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.api.email}"
}
