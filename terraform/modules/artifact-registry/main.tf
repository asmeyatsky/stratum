resource "google_artifact_registry_repository" "main" {
  location      = var.region
  project       = var.project_id
  repository_id = "${var.name_prefix}-docker"
  format        = "DOCKER"
  description   = "Stratum container images"
  labels        = var.labels

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"

    most_recent_versions {
      keep_count = 10
    }
  }
}
