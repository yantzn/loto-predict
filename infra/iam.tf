data "google_project" "current" {
  project_id = var.project_id
}

resource "google_storage_bucket_iam_member" "functions_runtime_raw_bucket_object_admin" {
  bucket = google_storage_bucket.raw_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_bigquery_dataset_iam_member" "functions_runtime_bigquery_data_editor" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_project_iam_member" "functions_runtime_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_project_iam_member" "functions_runtime_eventarc_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_project_iam_member" "functions_runtime_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_secret_manager_secret_iam_member" "functions_runtime_line_channel_access_token_accessor" {
  project   = var.project_id
  secret_id = var.line_channel_access_token_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_secret_manager_secret_iam_member" "functions_runtime_line_user_id_accessor" {
  project   = var.project_id
  secret_id = var.line_user_id_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_service_account_iam_member" "scheduler_service_agent_token_creator" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.scheduler_invoker_service_account_email}"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
}

resource "google_cloud_run_service_iam_member" "fetch_scheduler_invoker" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.fetch_loto_results.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.scheduler_invoker_service_account_email}"
}

resource "google_cloud_run_service_iam_member" "notify_scheduler_invoker" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.generate_prediction_and_notify.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.scheduler_invoker_service_account_email}"
}
