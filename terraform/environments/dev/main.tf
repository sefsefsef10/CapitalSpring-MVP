# Development Environment
# Main Terraform configuration for dev

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

# Configure providers
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Local values
locals {
  labels = {
    environment = "dev"
    project     = "capitalspring"
    managed_by  = "terraform"
  }
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "documentai.googleapis.com",
    "bigquery.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "firebase.googleapis.com",
    "identitytoolkit.googleapis.com",
    "servicenetworking.googleapis.com",
  ])

  project                    = var.project_id
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false
}

# Random password for database
resource "random_password" "db_password" {
  length  = 24
  special = false
}

# Store database password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "capitalspring-db-password"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

# Cloud SQL Module
module "cloudsql" {
  source = "../../modules/cloudsql"

  project_id        = var.project_id
  region            = var.region
  instance_name     = "capitalspring-dev"
  database_name     = "capitalspring"
  database_user     = "app"
  database_password = random_password.db_password.result

  tier              = "db-f1-micro"
  disk_size         = 10
  availability_type = "ZONAL"

  enable_public_ip = true
  require_ssl      = false # Disable for development

  deletion_protection = false # Allow deletion in dev

  labels = local.labels

  depends_on = [google_project_service.apis]
}

# Pub/Sub Module (create topics first)
module "pubsub" {
  source = "../../modules/pubsub"

  project_id               = var.project_id
  document_uploaded_topic  = "document-uploaded"
  document_processed_topic = "document-processed"

  # Placeholder endpoint - will be updated after Cloud Run deployment
  cloudrun_endpoint = "https://placeholder.run.app/api/v1/webhook/pubsub/document-uploaded"

  labels = local.labels

  depends_on = [google_project_service.apis]
}

# Storage Module
module "storage" {
  source = "../../modules/storage"

  project_id        = var.project_id
  bucket_name       = "${var.project_id}-data"
  location          = "US"
  force_destroy     = true # Allow deletion in dev
  enable_versioning = true

  pubsub_topic_id = module.pubsub.document_uploaded_topic_id

  cors_origins = ["http://localhost:3000", "http://localhost:5173"]

  labels = local.labels

  depends_on = [module.pubsub]
}

# Cloud Run Module
module "cloudrun" {
  source = "../../modules/cloudrun"

  project_id     = var.project_id
  region         = var.region
  service_name   = "capitalspring-api"
  container_image = "gcr.io/${var.project_id}/capitalspring-api:latest"

  min_instances = 0
  max_instances = 3
  cpu_limit     = "1"
  memory_limit  = "512Mi"

  create_service_account = true
  allow_unauthenticated  = true # For development

  environment_variables = {
    ENVIRONMENT                = "development"
    GCP_PROJECT_ID             = var.project_id
    GCS_BUCKET_NAME            = module.storage.bucket_name
    DATABASE_URL               = "postgresql+asyncpg://${module.cloudsql.database_user}:${random_password.db_password.result}@/${module.cloudsql.database_name}?host=/cloudsql/${module.cloudsql.instance_connection_name}"
    PUBSUB_DOCUMENT_UPLOADED_TOPIC  = "document-uploaded"
    PUBSUB_DOCUMENT_PROCESSED_TOPIC = "document-processed"
    LOG_LEVEL                  = "INFO"
  }

  secret_environment_variables = {
    ANTHROPIC_API_KEY = {
      secret_name = "anthropic-api-key"
      version     = "latest"
    }
  }

  cloudsql_connection_name = module.cloudsql.instance_connection_name

  labels = local.labels

  depends_on = [module.cloudsql, module.storage]
}
