# VPC network
resource "google_compute_network" "main" {
  name                    = "${var.name_prefix}-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false
}

# Private subnet for Cloud SQL and internal services
resource "google_compute_subnetwork" "private" {
  name          = "${var.name_prefix}-private"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = "10.0.0.0/20"

  private_ip_google_access = true
}

# VPC connector subnet for Cloud Run → VPC access
resource "google_compute_subnetwork" "connector" {
  name          = "${var.name_prefix}-connector"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = "10.8.0.0/28"
}

# Serverless VPC Access connector — lets Cloud Run reach Cloud SQL
resource "google_vpc_access_connector" "main" {
  name    = "${var.name_prefix}-conn"
  project = var.project_id
  region  = var.region

  subnet {
    name = google_compute_subnetwork.connector.name
  }

  min_instances = 2
  max_instances = 3
  machine_type  = "e2-micro"
}

# Private services access for Cloud SQL private IP
resource "google_compute_global_address" "private_ip_range" {
  name          = "${var.name_prefix}-private-ip"
  project       = var.project_id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

# Cloud NAT — outbound internet for VPC connector (API → external services)
resource "google_compute_router" "main" {
  name    = "${var.name_prefix}-router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.main.id
}

resource "google_compute_router_nat" "main" {
  name                               = "${var.name_prefix}-nat"
  project                            = var.project_id
  region                             = var.region
  router                             = google_compute_router.main.name
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
