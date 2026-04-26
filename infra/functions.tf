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
        object = google_storage_bucket_object.fetch_placeholder_source.name
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
      APP_ENV                 = "gcp"
      APP_TIMEZONE            = var.app_timezone
      GCP_PROJECT_ID          = var.project_id
      GCP_REGION              = var.region
      GCS_BUCKET_RAW          = google_storage_bucket.raw_bucket.name
      BQ_DATASET              = google_bigquery_dataset.dataset.dataset_id
      BQ_TABLE_EXECUTION_LOGS = google_bigquery_table.execution_logs.table_id
      PUBSUB_IMPORT_TOPIC     = google_pubsub_topic.import_requests.name
      LOG_LEVEL               = var.log_level
      LOG_EXECUTION_ID        = "true"
    }
  }

  lifecycle {
    ignore_changes = [
      build_config[0].source[0].storage_source[0].generation,
      service_config[0].environment_variables,
    ]
  }

  depends_on = [
    google_project_service.services,
    google_storage_bucket_object.fetch_placeholder_source,
    google_storage_bucket.raw_bucket,
    google_bigquery_dataset.dataset,
    google_bigquery_table.execution_logs,
    google_pubsub_topic.import_requests,
  ]
}

resource "google_cloudfunctions2_function" "import_loto_results_to_bq" {
  name     = "import-loto-results-to-bq-v2"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.runtime
    entry_point = "entry_point"

    source {
      storage_source {
        bucket = var.source_bucket_name
        object = google_storage_bucket_object.import_placeholder_source.name
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
      APP_ENV                  = "gcp"
      APP_TIMEZONE             = var.app_timezone
      BQ_DATASET               = google_bigquery_dataset.dataset.dataset_id
      BQ_TABLE_EXECUTION_LOGS  = google_bigquery_table.execution_logs.table_id
      BQ_TABLE_LOTO6_HISTORY   = google_bigquery_table.loto6_history.table_id
      BQ_TABLE_LOTO7_HISTORY   = google_bigquery_table.loto7_history.table_id
      BQ_TABLE_PREDICTION_RUNS = google_bigquery_table.prediction_runs.table_id
      GCP_PROJECT_ID           = var.project_id
      GCP_REGION               = var.region
      GCS_BUCKET_RAW           = google_storage_bucket.raw_bucket.name
      PUBSUB_NOTIFY_TOPIC      = google_pubsub_topic.notify_requests.name
      LOG_LEVEL                = var.log_level
      LOG_EXECUTION_ID         = "true"
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.import_requests.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }

  lifecycle {
    ignore_changes = [
      build_config[0].source[0].storage_source[0].generation,
      service_config[0].environment_variables,
    ]
  }

  depends_on = [
    google_project_service.services,
    google_storage_bucket_object.import_placeholder_source,
    google_storage_bucket.raw_bucket,
    google_bigquery_dataset.dataset,
    google_bigquery_table.execution_logs,
    google_bigquery_table.loto6_history,
    google_bigquery_table.loto7_history,
    google_bigquery_table.prediction_runs,
    google_pubsub_topic.import_requests,
    google_pubsub_topic.notify_requests,
  ]
}

resource "google_cloudfunctions2_function" "generate_prediction_and_notify" {
  name     = "generate-prediction-and-notify-v2"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.runtime
    entry_point = "entry_point"

    source {
      storage_source {
        bucket = var.source_bucket_name
        object = google_storage_bucket_object.notify_placeholder_source.name
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
      APP_ENV                  = "gcp"
      APP_TIMEZONE             = var.app_timezone
      BQ_DATASET               = google_bigquery_dataset.dataset.dataset_id
      BQ_TABLE_EXECUTION_LOGS  = google_bigquery_table.execution_logs.table_id
      BQ_TABLE_LOTO6_HISTORY   = google_bigquery_table.loto6_history.table_id
      BQ_TABLE_LOTO7_HISTORY   = google_bigquery_table.loto7_history.table_id
      BQ_TABLE_PREDICTION_RUNS = google_bigquery_table.prediction_runs.table_id
      GCP_PROJECT_ID           = var.project_id
      GCP_REGION               = var.region
      HISTORY_LIMIT_LOTO6      = tostring(var.history_limit_loto6)
      HISTORY_LIMIT_LOTO7      = tostring(var.history_limit_loto7)
      LOG_LEVEL                = var.log_level
      LOG_EXECUTION_ID         = "true"
    }

    secret_environment_variables {
      key        = "LINE_CHANNEL_ACCESS_TOKEN"
      project_id = var.project_id
      secret     = var.line_channel_access_token_secret_id
      version    = var.line_channel_access_token_secret_version
    }

    secret_environment_variables {
      key        = "LINE_USER_ID"
      project_id = var.project_id
      secret     = var.line_user_id_secret_id
      version    = var.line_user_id_secret_version
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.notify_requests.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }

  lifecycle {
    ignore_changes = [
      build_config[0].source[0].storage_source[0].generation,
      service_config[0].environment_variables,
    ]
  }

  depends_on = [
    google_project_service.services,
    google_storage_bucket_object.notify_placeholder_source,
    google_bigquery_dataset.dataset,
    google_bigquery_table.execution_logs,
    google_bigquery_table.loto6_history,
    google_bigquery_table.loto7_history,
    google_bigquery_table.prediction_runs,
    google_pubsub_topic.notify_requests,
  ]
}
