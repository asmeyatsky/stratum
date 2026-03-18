output "connection_name" {
  value = google_sql_database_instance.main.connection_name
}

output "private_ip" {
  value = google_sql_database_instance.main.private_ip_address
}

output "database_name" {
  value = google_sql_database.stratum.name
}

output "database_user" {
  value = google_sql_user.stratum.name
}

output "instance_name" {
  value = google_sql_database_instance.main.name
}
