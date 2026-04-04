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
      LOG_LEVEL      = var.log_level
    }
  }

  depends_on = [
    google_project_service.services,
    google_storage_bucket.raw_bucket,
  ]
}

resource "google_cloudfunctions2_function" "import_loto_results_to_bq" {
  name     = "import-loto-results-to-bq"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.runtime
    entry_point = "import_loto_results"

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
      GCP_PROJECT_ID           = var.project_id
      BQ_DATASET               = var.dataset_id
      BQ_TABLE_LOTO6_HISTORY   = google_bigquery_table.loto6_history.table_id
      BQ_TABLE_LOTO7_HISTORY   = google_bigquery_table.loto7_history.table_id
      BQ_STAGING_TABLE_LOTO6   = google_bigquery_table.loto6_history_staging.table_id
      BQ_STAGING_TABLE_LOTO7   = google_bigquery_table.loto7_history_staging.table_id
      BQ_TABLE_PREDICTION_RUNS = google_bigquery_table.prediction_runs.table_id
      LOG_LEVEL                = var.log_level
    }
  }

  depends_on = [
    google_project_service.services,
    google_bigquery_dataset.dataset,
    google_bigquery_table.loto6_history,
    google_bigquery_table.loto7_history,
    google_bigquery_table.loto6_history_staging,
    google_bigquery_table.loto7_history_staging,
    google_bigquery_table.prediction_runs,
  ]
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
      BQ_DATASET               = var.dataset_id
      BQ_TABLE_LOTO6_HISTORY   = google_bigquery_table.loto6_history.table_id
      BQ_TABLE_LOTO7_HISTORY   = google_bigquery_table.loto7_history.table_id
      BQ_TABLE_PREDICTION_RUNS = google_bigquery_table.prediction_runs.table_id
      HISTORY_LIMIT_LOTO6      = tostring(var.history_limit_loto6)
      HISTORY_LIMIT_LOTO7      = tostring(var.history_limit_loto7)
      LOG_LEVEL                = var.log_level
    }

    secret_environment_variables {
      key        = "LINE_CHANNEL_ACCESS_TOKEN"
      project_id = var.project_id
      secret     = var.line_channel_access_token_secret_id
      version    = "latest"
    }

    secret_environment_variables {
      key        = "LINE_TO_USER_ID"
      project_id = var.project_id
      secret     = var.line_user_id_secret_id
      version    = "latest"
    }
  }

  depends_on = [
    google_project_service.services,
    google_bigquery_dataset.dataset,
    google_bigquery_table.loto6_history,
    google_bigquery_table.loto7_history,
    google_bigquery_table.prediction_runs,
  ]
}
