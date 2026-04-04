output "dataset_id" {
  value = google_bigquery_dataset.dataset.dataset_id
}

output "function_name" {
  value = google_cloudfunctions2_function.loto_orchestrator.name
}

output "function_uri" {
  value = google_cloudfunctions2_function.loto_orchestrator.service_config[0].uri
}

output "line_channel_access_token_secret_id" {
  value = google_secret_manager_secret.line_channel_access_token.secret_id
}

output "line_user_id_secret_id" {
  value = google_secret_manager_secret.line_user_id.secret_id
}

output "loto6_scheduler_job_name" {
  value = google_cloud_scheduler_job.loto6_job.name
}

output "loto7_scheduler_job_name" {
  value = google_cloud_scheduler_job.loto7_job.name
}

output "fetch_function_source_object" {
  value = var.fetch_function_source_object
}
output "import_function_source_object" {
  value = var.import_function_source_object
}
output "notify_function_source_object" {
  value = var.notify_function_source_object
}
