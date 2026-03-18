# GCS bucket for the React SPA static files
resource "google_storage_bucket" "frontend" {
  name          = "${var.name_prefix}-frontend"
  project       = var.project_id
  location      = "US"
  force_destroy = false
  labels        = var.labels

  uniform_bucket_level_access = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html" # SPA client-side routing
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }
}

# Make the bucket publicly readable
resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.frontend.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Cloud CDN backend bucket
resource "google_compute_backend_bucket" "frontend" {
  name        = "${var.name_prefix}-frontend-backend"
  project     = var.project_id
  bucket_name = google_storage_bucket.frontend.name
  enable_cdn  = true

  cdn_policy {
    cache_mode                   = "CACHE_ALL_STATIC"
    default_ttl                  = 3600
    max_ttl                      = 86400
    negative_caching             = true
    serve_while_stale            = 86400
    signed_url_cache_max_age_sec = 0
  }
}

# URL map
resource "google_compute_url_map" "frontend" {
  name            = "${var.name_prefix}-frontend-urlmap"
  project         = var.project_id
  default_service = google_compute_backend_bucket.frontend.id
}

# HTTP proxy (redirects to HTTPS if SSL cert is configured)
resource "google_compute_target_http_proxy" "frontend" {
  name    = "${var.name_prefix}-frontend-http"
  project = var.project_id
  url_map = google_compute_url_map.frontend.id
}

# Global forwarding rule (HTTP)
resource "google_compute_global_forwarding_rule" "frontend_http" {
  name        = "${var.name_prefix}-frontend-http-rule"
  project     = var.project_id
  target      = google_compute_target_http_proxy.frontend.id
  port_range  = "80"
  ip_protocol = "TCP"
}

# Optional: HTTPS with managed SSL certificate (only when domain is set)
resource "google_compute_managed_ssl_certificate" "frontend" {
  count   = var.domain != "" ? 1 : 0
  name    = "${var.name_prefix}-frontend-cert"
  project = var.project_id

  managed {
    domains = [var.domain]
  }
}

resource "google_compute_target_https_proxy" "frontend" {
  count   = var.domain != "" ? 1 : 0
  name    = "${var.name_prefix}-frontend-https"
  project = var.project_id
  url_map = google_compute_url_map.frontend.id

  ssl_certificates = [google_compute_managed_ssl_certificate.frontend[0].id]
}

resource "google_compute_global_forwarding_rule" "frontend_https" {
  count       = var.domain != "" ? 1 : 0
  name        = "${var.name_prefix}-frontend-https-rule"
  project     = var.project_id
  target      = google_compute_target_https_proxy.frontend[0].id
  port_range  = "443"
  ip_protocol = "TCP"
}
