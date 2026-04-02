#
# Scheduler SA must be able to invoke the underlying Cloud Run service
# for Gen2 Cloud Functions.
#
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  location = var.region
  service  = google_cloudfunctions2_function.loto_orchestrator.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.scheduler_invoker_service_account_email}"
}
