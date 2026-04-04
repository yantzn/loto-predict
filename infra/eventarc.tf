resource "google_eventarc_trigger" "import_loto_results_gcs" {
  name     = "import-loto-results-gcs"
  location = var.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.raw_bucket.name
  }

  service_account = var.functions_runtime_service_account_email

  destination {
    cloud_function {
      function = google_cloudfunctions2_function.import_loto_results_to_bq.name
    }
  }

  depends_on = [
    google_project_service.services,
    google_storage_bucket.raw_bucket,
    google_cloudfunctions2_function.import_loto_results_to_bq
  ]
}
