# Cloud Run Module Outputs

output "service_name" {
  description = "Name of the Cloud Run service"
  value       = google_cloud_run_v2_service.api.name
}

output "service_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.api.uri
}

output "service_account_email" {
  description = "Service account email"
  value       = var.create_service_account ? google_service_account.cloudrun[0].email : var.service_account_email
}

output "webhook_endpoint" {
  description = "Webhook endpoint for Pub/Sub"
  value       = "${google_cloud_run_v2_service.api.uri}/api/v1/webhook/pubsub/document-uploaded"
}
