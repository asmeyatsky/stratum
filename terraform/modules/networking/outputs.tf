output "network_id" {
  value = google_compute_network.main.id
}

output "network_name" {
  value = google_compute_network.main.name
}

output "private_subnet_id" {
  value = google_compute_subnetwork.private.id
}

output "vpc_connector_id" {
  value = google_vpc_access_connector.main.id
}
