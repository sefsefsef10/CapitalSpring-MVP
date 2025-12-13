# Terraform Backend Configuration
# Uses GCS for remote state storage

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
  }

  # GCS backend for remote state storage
  backend "gcs" {
    bucket = "capitalspring-terraform-state"
    prefix = "terraform/state"
  }
}
