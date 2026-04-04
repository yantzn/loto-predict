resource "google_cloudfunctions2_function" "fetch_loto_results" {
  name     = "fetch-loto-results"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.runtime
    entry_point = "fetch_loto_results"

    source {
      storage_source {
        bucket = var.source_bucket_name
        object = var.fetch_function_source_object
      }
    }
  }

  service_config {
    timeout_seconds       = var.function_timeout_seconds
    available_memory      = var.function_available_memory
    min_instance_count    = 0
    max_instance_count    = 1
    ingress_settings      = "ALLOW_ALL"
    service_account_email = var.functions_runtime_service_account_email

    environment_variables = {
      GCP_PROJECT_ID = var.project_id
      GCS_BUCKET_RAW = google_storage_bucket.raw_bucket.name
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [google_project_service.services]
}

resource "google_cloudfunctions2_function" "import_loto_results_to_bq" {
  name     = "import-loto-results-to-bq"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.runtime
    entry_point = "import_loto_results_http"

    source {
      storage_source {
        bucket = var.source_bucket_name
        object = var.import_function_source_object
      }
    }
  }

  service_config {
    timeout_seconds       = 300
    available_memory      = "512M"
    min_instance_count    = 0
    max_instance_count    = 1
    ingress_settings      = "ALLOW_ALL"
    service_account_email = var.functions_runtime_service_account_email

    environment_variables = {
      GCP_PROJECT_ID          = var.project_id
      BQ_DATASET              = var.bigquery_dataset_id
      BQ_TABLE_LOTO6_HISTORY  = var.loto6_history_table_id
      BQ_TABLE_LOTO7_HISTORY  = var.loto7_history_table_id
      BQ_STAGING_TABLE_LOTO6  = var.loto6_staging_table_id
      BQ_STAGING_TABLE_LOTO7  = var.loto7_staging_table_id
      BQ_TABLE_PREDICTION_RUNS = var.prediction_runs_table_id
      LOG_LEVEL               = "INFO"
    }
  }

  depends_on = [google_project_service.services]
}

resource "google_cloudfunctions2_function" "generate_prediction_and_notify" {
  name     = "generate-prediction-and-notify"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.runtime
    entry_point = "generate_prediction_and_notify"

    source {
      storage_source {
        bucket = var.source_bucket_name
        object = var.notify_function_source_object
      }
    }
  }

  service_config {
    timeout_seconds       = var.function_timeout_seconds
    available_memory      = var.function_available_memory
    min_instance_count    = 0
    max_instance_count    = 1
    ingress_settings      = "ALLOW_ALL"
    service_account_email = var.functions_runtime_service_account_email

    environment_variables = {
      GCP_PROJECT_ID           = var.project_id
      BQ_DATASET               = var.bigquery_dataset_id
      BQ_TABLE_LOTO6_HISTORY   = var.loto6_history_table_id
      BQ_TABLE_LOTO7_HISTORY   = var.loto7_history_table_id
      BQ_TABLE_PREDICTION_RUNS = var.prediction_runs_table_id
      HISTORY_LIMIT_LOTO6      = tostring(var.history_limit_loto6)
      HISTORY_LIMIT_LOTO7      = tostring(var.history_limit_loto7)
      LINE_CHANNEL_ACCESS_TOKEN = var.line_channel_access_token
      LINE_TO_USER_ID           = var.line_to_user_id
      LOG_LEVEL                 = "INFO"
    }
  }

  depends_on = [google_project_service.services]
}
