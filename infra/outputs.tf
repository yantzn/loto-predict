output "raw_bucket_name" {
  value = google_storage_bucket.raw_bucket.name
}

output "source_bucket_name" {
  value = var.source_bucket_name
}

output "fetch_function_name" {
  value = google_cloudfunctions2_function.fetch_loto_results.name
}

output "import_function_name" {
  value = google_cloudfunctions2_function.import_loto_results_to_bq.name
}

output "notify_function_name" {
  value = google_cloudfunctions2_function.generate_prediction_and_notify.name
}

output "backfill_job_name" {
  value = google_cloud_run_v2_job.backfill_loto_history.name
}
