resource "google_project_iam_member" "functions_runtime_storage_object_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_project_iam_member" "functions_runtime_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${var.functions_runtime_service_account_email}"
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

resource "google_project_iam_member" "functions_runtime_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_project_iam_member" "scheduler_invoker_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${var.scheduler_invoker_service_account_email}"
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

resource "google_cloud_run_service_iam_member" "import_scheduler_invoker" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.import_loto_results_to_bq.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.scheduler_invoker_service_account_email}"
}
