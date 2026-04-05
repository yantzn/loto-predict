resource "google_cloudfunctions2_function" "fetch_loto_results" {
  name     = "fetch-loto-results"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.runtime
    entry_point = "entry_point"

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
    min_instance_count    = var.function_min_instance_count
    max_instance_count    = var.function_max_instance_count
    ingress_settings      = "ALLOW_ALL"
    service_account_email = var.functions_runtime_service_account_email

    environment_variables = {
      GCP_PROJECT_ID      = var.project_id
      GCP_REGION          = var.region
      APP_TIMEZONE        = var.app_timezone
      GCS_BUCKET_RAW      = google_storage_bucket.raw_bucket.name
      PUBSUB_IMPORT_TOPIC = google_pubsub_topic.import_requests.name
      LOG_LEVEL           = var.log_level
    }
  }

  depends_on = [
    google_project_service.services,
    google_storage_bucket.raw_bucket,
    google_pubsub_topic.import_requests,
  ]
}

resource "google_cloudfunctions2_function" "import_loto_results_to_bq" {
  name     = "import-loto-results-to-bq"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.runtime
    entry_point = "entry_point"

    source {
      storage_source {
        bucket = var.source_bucket_name
        object = var.import_function_source_object
      }
    }
  }

  service_config {
    timeout_seconds       = 300
    available_memory      = var.function_available_memory
    min_instance_count    = var.function_min_instance_count
    max_instance_count    = var.function_max_instance_count
    ingress_settings      = "ALLOW_ALL"
    service_account_email = var.functions_runtime_service_account_email

    environment_variables = {
      GCP_PROJECT_ID            = var.project_id
      GCP_REGION                = var.region
      APP_TIMEZONE              = var.app_timezone
      GCS_BUCKET_RAW            = google_storage_bucket.raw_bucket.name
      BIGQUERY_DATASET          = google_bigquery_dataset.dataset.dataset_id
      BQ_TABLE_LOTO6_HISTORY    = google_bigquery_table.loto6_history.table_id
      BQ_TABLE_LOTO7_HISTORY    = google_bigquery_table.loto7_history.table_id
      BQ_TABLE_LOTO6_VALIDATION = google_bigquery_table.loto6_validation_stage.table_id
      BQ_TABLE_LOTO7_VALIDATION = google_bigquery_table.loto7_validation_stage.table_id
      PUBSUB_NOTIFY_TOPIC       = google_pubsub_topic.notify_requests.name
      LOG_LEVEL                 = var.log_level
    }
  }

  depends_on = [
    google_project_service.services,
    google_storage_bucket.raw_bucket,
    google_bigquery_dataset.dataset,
    google_bigquery_table.loto6_history,
    google_bigquery_table.loto7_history,
    google_bigquery_table.loto6_validation_stage,
    google_bigquery_table.loto7_validation_stage,
    google_pubsub_topic.notify_requests,
  ]
}

resource "google_cloudfunctions2_function" "generate_prediction_and_notify" {
  name     = "generate-prediction-and-notify"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.runtime
    entry_point = "entry_point"

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
    min_instance_count    = var.function_min_instance_count
    max_instance_count    = var.function_max_instance_count
    ingress_settings      = "ALLOW_ALL"
    service_account_email = var.functions_runtime_service_account_email

    environment_variables = {
      GCP_PROJECT_ID           = var.project_id
      GCP_REGION               = var.region
      APP_TIMEZONE             = var.app_timezone
      BIGQUERY_DATASET         = google_bigquery_dataset.dataset.dataset_id
      BQ_TABLE_LOTO6_HISTORY   = google_bigquery_table.loto6_history.table_id
      BQ_TABLE_LOTO7_HISTORY   = google_bigquery_table.loto7_history.table_id
      BQ_TABLE_PREDICTION_RUNS = google_bigquery_table.prediction_runs.table_id
      BQ_TABLE_EXECUTION_LOGS  = google_bigquery_table.execution_logs.table_id
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
    google_bigquery_table.execution_logs,
  ]
}
