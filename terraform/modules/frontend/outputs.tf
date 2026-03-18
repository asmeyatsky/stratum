output "bucket_name" {
  value = google_storage_bucket.frontend.name
}

output "cdn_url" {
  value = var.domain != "" ? "https://${var.domain}" : "http://${google_compute_global_forwarding_rule.frontend_http.ip_address}"
}

output "cdn_ip" {
  value = google_compute_global_forwarding_rule.frontend_http.ip_address
}
