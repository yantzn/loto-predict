output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.dataset.dataset_id
}

output "raw_bucket_name" {
  description = "Raw result bucket name"
  value       = google_storage_bucket.raw_bucket.name
}

output "fetch_function_name" {
  description = "Cloud Function name for fetch_loto_results"
  value       = google_cloudfunctions2_function.fetch_loto_results.name
}

output "fetch_function_uri" {
  description = "Cloud Function URI for fetch_loto_results"
  value       = google_cloudfunctions2_function.fetch_loto_results.service_config[0].uri
}

output "import_function_name" {
  description = "Cloud Function name for import_loto_results_to_bq"
  value       = google_cloudfunctions2_function.import_loto_results_to_bq.name
}

output "import_function_uri" {
  description = "Cloud Function URI for import_loto_results_to_bq"
  value       = google_cloudfunctions2_function.import_loto_results_to_bq.service_config[0].uri
}

output "notify_function_name" {
  description = "Cloud Function name for generate_prediction_and_notify"
  value       = google_cloudfunctions2_function.generate_prediction_and_notify.name
}

output "notify_function_uri" {
  description = "Cloud Function URI for generate_prediction_and_notify"
  value       = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
}

output "fetch_loto6_job_name" {
  description = "Scheduler job name for loto6 fetch"
  value       = google_cloud_scheduler_job.fetch_loto6_job.name
}

output "fetch_loto7_job_name" {
  description = "Scheduler job name for loto7 fetch"
  value       = google_cloud_scheduler_job.fetch_loto7_job.name
}

output "import_requests_topic_name" {
  description = "Pub/Sub topic name for import requests"
  value       = google_pubsub_topic.import_requests.name
}

output "notify_requests_topic_name" {
  description = "Pub/Sub topic name for notify requests"
  value       = google_pubsub_topic.notify_requests.name
}

output "import_requests_subscription_name" {
  description = "Pub/Sub push subscription name for import requests"
  value       = google_pubsub_subscription.import_requests_push.name
}

output "notify_requests_subscription_name" {
  description = "Pub/Sub push subscription name for notify requests"
  value       = google_pubsub_subscription.notify_requests_push.name
}

output "table_ids" {
  description = "BigQuery table IDs used by this system"
  value = {
    loto6_history          = google_bigquery_table.loto6_history.table_id
    loto7_history          = google_bigquery_table.loto7_history.table_id
    loto6_validation_stage = google_bigquery_table.loto6_validation_stage.table_id
    loto7_validation_stage = google_bigquery_table.loto7_validation_stage.table_id
    prediction_runs        = google_bigquery_table.prediction_runs.table_id
    execution_logs         = google_bigquery_table.execution_logs.table_id
  }
}
