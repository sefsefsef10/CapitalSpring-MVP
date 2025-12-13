# Pub/Sub Module
# Creates topics and subscriptions for event-driven processing

# Document uploaded topic
resource "google_pubsub_topic" "document_uploaded" {
  name    = var.document_uploaded_topic
  project = var.project_id

  labels = var.labels

  message_retention_duration = "86400s" # 24 hours
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "dead_letter" {
  name    = "${var.document_uploaded_topic}-dlq"
  project = var.project_id

  labels = var.labels
}

# Push subscription to Cloud Run
resource "google_pubsub_subscription" "document_uploaded_push" {
  name    = "${var.document_uploaded_topic}-push"
  topic   = google_pubsub_topic.document_uploaded.name
  project = var.project_id

  # Push configuration
  push_config {
    push_endpoint = var.cloudrun_endpoint

    attributes = {
      x-goog-version = "v1"
    }

    # OIDC authentication
    dynamic "oidc_token" {
      for_each = var.push_service_account != "" ? [1] : []
      content {
        service_account_email = var.push_service_account
      }
    }
  }

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead letter policy
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  # Acknowledgement deadline
  ack_deadline_seconds = 60

  # Message retention
  message_retention_duration = "604800s" # 7 days

  # Expiration policy (never expire)
  expiration_policy {
    ttl = ""
  }

  labels = var.labels
}

# Dead letter subscription for monitoring
resource "google_pubsub_subscription" "dead_letter_sub" {
  name    = "${var.document_uploaded_topic}-dlq-sub"
  topic   = google_pubsub_topic.dead_letter.name
  project = var.project_id

  message_retention_duration = "604800s" # 7 days
  retain_acked_messages      = true

  labels = var.labels
}

# Document processed topic (for downstream integrations)
resource "google_pubsub_topic" "document_processed" {
  name    = var.document_processed_topic
  project = var.project_id

  labels = var.labels

  message_retention_duration = "86400s"
}

# IAM: Allow Cloud Run to publish to processed topic
resource "google_pubsub_topic_iam_member" "cloudrun_publisher" {
  count  = var.cloudrun_service_account != "" ? 1 : 0
  topic  = google_pubsub_topic.document_processed.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${var.cloudrun_service_account}"
}
