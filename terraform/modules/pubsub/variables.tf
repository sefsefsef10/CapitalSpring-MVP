# Pub/Sub Module Variables

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "document_uploaded_topic" {
  description = "Topic name for document uploaded events"
  type        = string
  default     = "document-uploaded"
}

variable "document_processed_topic" {
  description = "Topic name for document processed events"
  type        = string
  default     = "document-processed"
}

variable "cloudrun_endpoint" {
  description = "Cloud Run endpoint URL for push subscription"
  type        = string
}

variable "push_service_account" {
  description = "Service account for OIDC authentication"
  type        = string
  default     = ""
}

variable "cloudrun_service_account" {
  description = "Cloud Run service account for IAM"
  type        = string
  default     = ""
}

variable "labels" {
  description = "Labels to apply to resources"
  type        = map(string)
  default     = {}
}
