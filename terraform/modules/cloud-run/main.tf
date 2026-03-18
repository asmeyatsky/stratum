resource "google_cloud_run_v2_service" "api" {
  name     = "${var.name_prefix}-api"
  project  = var.project_id
  location = var.region
  labels   = var.labels

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle          = var.min_instances == 0
        startup_cpu_boost = true
      }

      ports {
        container_port = 8000
      }

      # Application environment
      env {
        name  = "STRATUM_ENV"
        value = "production"
      }

      env {
        name  = "STRATUM_PORT"
        value = "8000"
      }

      env {
        name  = "STRATUM_WORKERS"
        value = "2"
      }

      env {
        name  = "STRATUM_LOG_LEVEL"
        value = "info"
      }

      # Database — Cloud SQL via Unix socket
      env {
        name  = "DB_HOST"
        value = "/cloudsql/${var.db_connection_name}"
      }

      env {
        name  = "DB_NAME"
        value = var.db_name
      }

      env {
        name  = "DB_USER"
        value = var.db_user
      }

      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.db_password_secret
            version = "latest"
          }
        }
      }

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = var.gemini_key_secret
            version = "latest"
          }
        }
      }

      # CORS — allow frontend CDN origin
      env {
        name  = "CORS_ORIGINS"
        value = "*" # Tightened after custom domain is configured
      }

      startup_probe {
        http_get {
          path = "/api/health"
          port = 8000
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 10
        timeout_seconds       = 3
      }

      liveness_probe {
        http_get {
          path = "/api/health"
          port = 8000
        }
        period_seconds    = 30
        failure_threshold = 3
        timeout_seconds   = 5
      }
    }

    # Cloud SQL Auth Proxy sidecar — provides Unix socket for DB connection
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [var.db_connection_name]
      }
    }

    timeout = "300s"
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Allow unauthenticated access (API handles its own auth via JWT)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
