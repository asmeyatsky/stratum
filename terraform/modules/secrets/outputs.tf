output "db_password_secret_id" {
  value = google_secret_manager_secret.db_password.id
}

output "gemini_key_secret_id" {
  value = google_secret_manager_secret.gemini_key.id
}

output "jwt_secret_id" {
  value = google_secret_manager_secret.jwt_secret.id
}
