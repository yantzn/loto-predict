resource "google_eventarc_trigger" "import_loto_results_gcs" {
  name     = "import-loto-results-gcs"
  location = var.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = var.raw_bucket_name
  }

  service_account = var.functions_runtime_service_account_email

  destination {
    cloud_function {
      function = google_cloudfunctions2_function.import_loto_results_to_bq.name
    }
  }
}
