# Cloud Storage Module
# Creates buckets for document storage with Pub/Sub notifications

resource "google_storage_bucket" "data_bucket" {
  name          = var.bucket_name
  location      = var.location
  project       = var.project_id
  force_destroy = var.force_destroy

  # Uniform bucket-level access
  uniform_bucket_level_access = true

  # Versioning
  versioning {
    enabled = var.enable_versioning
  }

  # Lifecycle rules
  lifecycle_rule {
    condition {
      age = 90
      matches_prefix = ["archive/"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 365
      matches_prefix = ["archive/"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 30
      matches_prefix = ["failed/"]
    }
    action {
      type = "Delete"
    }
  }

  # CORS configuration for uploads
  cors {
    origin          = var.cors_origins
    method          = ["GET", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  labels = var.labels
}

# Create folder structure by uploading placeholder objects
resource "google_storage_bucket_object" "inbox_placeholder" {
  name    = "inbox/.keep"
  content = ""
  bucket  = google_storage_bucket.data_bucket.name
}

resource "google_storage_bucket_object" "processing_placeholder" {
  name    = "processing/.keep"
  content = ""
  bucket  = google_storage_bucket.data_bucket.name
}

resource "google_storage_bucket_object" "complete_placeholder" {
  name    = "complete/.keep"
  content = ""
  bucket  = google_storage_bucket.data_bucket.name
}

resource "google_storage_bucket_object" "failed_placeholder" {
  name    = "failed/.keep"
  content = ""
  bucket  = google_storage_bucket.data_bucket.name
}

resource "google_storage_bucket_object" "archive_placeholder" {
  name    = "archive/.keep"
  content = ""
  bucket  = google_storage_bucket.data_bucket.name
}

resource "google_storage_bucket_object" "exports_placeholder" {
  name    = "exports/.keep"
  content = ""
  bucket  = google_storage_bucket.data_bucket.name
}

# Pub/Sub notification for new uploads in inbox/
resource "google_storage_notification" "inbox_notification" {
  bucket         = google_storage_bucket.data_bucket.name
  payload_format = "JSON_API_V1"
  topic          = var.pubsub_topic_id
  event_types    = ["OBJECT_FINALIZE"]

  object_name_prefix = "inbox/"

  depends_on = [google_pubsub_topic_iam_member.storage_publisher]
}

# Allow GCS to publish to Pub/Sub
data "google_storage_project_service_account" "gcs_account" {
  project = var.project_id
}

resource "google_pubsub_topic_iam_member" "storage_publisher" {
  topic  = var.pubsub_topic_id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

# IAM binding for Cloud Run service account
resource "google_storage_bucket_iam_member" "cloudrun_access" {
  count  = var.cloudrun_service_account != "" ? 1 : 0
  bucket = google_storage_bucket.data_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.cloudrun_service_account}"
}
