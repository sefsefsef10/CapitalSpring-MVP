# Storage Module Outputs

output "bucket_name" {
  description = "Name of the created bucket"
  value       = google_storage_bucket.data_bucket.name
}

output "bucket_url" {
  description = "URL of the bucket"
  value       = google_storage_bucket.data_bucket.url
}

output "bucket_self_link" {
  description = "Self link of the bucket"
  value       = google_storage_bucket.data_bucket.self_link
}
