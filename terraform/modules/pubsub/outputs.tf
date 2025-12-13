# Pub/Sub Module Outputs

output "document_uploaded_topic_id" {
  description = "ID of the document uploaded topic"
  value       = google_pubsub_topic.document_uploaded.id
}

output "document_uploaded_topic_name" {
  description = "Name of the document uploaded topic"
  value       = google_pubsub_topic.document_uploaded.name
}

output "document_processed_topic_id" {
  description = "ID of the document processed topic"
  value       = google_pubsub_topic.document_processed.id
}

output "dead_letter_topic_id" {
  description = "ID of the dead letter topic"
  value       = google_pubsub_topic.dead_letter.id
}

output "push_subscription_name" {
  description = "Name of the push subscription"
  value       = google_pubsub_subscription.document_uploaded_push.name
}
