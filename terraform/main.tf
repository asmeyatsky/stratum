# =============================================================================
# Stratum — GCP Infrastructure
# =============================================================================

locals {
  name_prefix = "stratum-${var.environment}"
  labels = {
    app         = "stratum"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ── IAM (service accounts) ──────────────────────────────────────────────────

module "iam" {
  source = "./modules/iam"

  project_id  = var.project_id
  name_prefix = local.name_prefix
}

# ── Networking ──────────────────────────────────────────────────────────────

module "networking" {
  source = "./modules/networking"

  project_id  = var.project_id
  region      = var.region
  name_prefix = local.name_prefix
}

# ── Secrets ─────────────────────────────────────────────────────────────────

module "secrets" {
  source = "./modules/secrets"

  project_id              = var.project_id
  name_prefix             = local.name_prefix
  api_service_account_email = module.iam.api_service_account_email
}

# ── Database (Cloud SQL PostgreSQL) ─────────────────────────────────────────

module "database" {
  source = "./modules/database"

  project_id          = var.project_id
  region              = var.region
  name_prefix         = local.name_prefix
  network_id          = module.networking.network_id
  tier                = var.db_tier
  ha_enabled          = var.db_ha
  db_password_secret  = module.secrets.db_password_secret_id
  labels              = local.labels
}

# ── Artifact Registry ──────────────────────────────────────────────────────

module "artifact_registry" {
  source = "./modules/artifact-registry"

  project_id  = var.project_id
  region      = var.region
  name_prefix = local.name_prefix
  labels      = local.labels
}

# ── Cloud Run (API) ────────────────────────────────────────────────────────

module "cloud_run" {
  source = "./modules/cloud-run"

  project_id    = var.project_id
  region        = var.region
  name_prefix   = local.name_prefix
  labels        = local.labels
  image         = var.api_image != "" ? var.api_image : "${module.artifact_registry.repository_url}/api:latest"
  cpu           = var.api_cpu
  memory        = var.api_memory
  min_instances = var.api_min_instances
  max_instances = var.api_max_instances

  vpc_connector_id          = module.networking.vpc_connector_id
  db_connection_name        = module.database.connection_name
  db_name                   = module.database.database_name
  db_user                   = module.database.database_user
  db_password_secret        = module.secrets.db_password_secret_id
  gemini_key_secret         = module.secrets.gemini_key_secret_id
  service_account_email     = module.iam.api_service_account_email

  depends_on = [module.database, module.secrets, module.networking]
}

# ── Frontend (GCS + CDN) ───────────────────────────────────────────────────

module "frontend" {
  source = "./modules/frontend"

  project_id  = var.project_id
  name_prefix = local.name_prefix
  labels      = local.labels
  domain      = var.domain
}
