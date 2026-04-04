data "google_secret_manager_secret" "line_channel_access_token" {
  project   = var.project_id
  secret_id = var.line_channel_access_token_secret_id
}

data "google_secret_manager_secret" "line_user_id" {
  project   = var.project_id
  secret_id = var.line_user_id_secret_id
}

resource "google_cloudfunctions2_function" "fetch_loto_results" {
  name     = "fetch-loto-results"
  location = var.region

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
      APP_ENV         = var.app_env
      APP_TIMEZONE    = var.app_timezone
      GCP_PROJECT_ID  = var.project_id
      GCP_REGION      = var.region
      RAW_BUCKET_NAME = google_storage_bucket.raw_bucket.name
      LOG_LEVEL       = var.log_level
      LOG_JSON        = var.log_json
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
    timeout_seconds       = var.function_timeout_seconds
    available_memory      = var.function_available_memory
    min_instance_count    = var.function_min_instance_count
    max_instance_count    = var.function_max_instance_count
    ingress_settings      = "ALLOW_ALL"
    service_account_email = var.functions_runtime_service_account_email

    environment_variables = {
      APP_ENV          = var.app_env
      APP_TIMEZONE     = var.app_timezone
      GCP_PROJECT_ID   = var.project_id
      GCP_REGION       = var.region
      BIGQUERY_DATASET = google_bigquery_dataset.dataset.dataset_id
        BIGQUERY_DATASET = var.bq_dataset
      RAW_BUCKET_NAME  = google_storage_bucket.raw_bucket.name
      LOG_LEVEL        = var.log_level
      LOG_JSON         = var.log_json
    }
  }

  depends_on = [
    google_project_service.services,
    google_bigquery_dataset.dataset,
    google_storage_bucket.raw_bucket,
  ]
}

resource "google_cloudfunctions2_function" "generate_prediction_and_notify" {
  name     = "generate-prediction-and-notify"
  location = var.region

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
      APP_ENV             = var.app_env
      APP_TIMEZONE        = var.app_timezone
      GCP_PROJECT_ID      = var.project_id
      GCP_REGION          = var.region
      BIGQUERY_DATASET    = google_bigquery_dataset.dataset.dataset_id
        BIGQUERY_DATASET    = var.bq_dataset
      HISTORY_LIMIT_LOTO6 = tostring(var.history_limit_loto6)
      HISTORY_LIMIT_LOTO7 = tostring(var.history_limit_loto7)
      LOG_LEVEL           = var.log_level
      LOG_JSON            = var.log_json
    }

    secret_environment_variables {
      key        = "LINE_CHANNEL_ACCESS_TOKEN"
      project_id = var.project_id
      secret     = data.google_secret_manager_secret.line_channel_access_token.secret_id
      version    = "latest"
    }

    secret_environment_variables {
      key        = "LINE_USER_ID"
      project_id = var.project_id
      secret     = data.google_secret_manager_secret.line_user_id.secret_id
      version    = "latest"
    }
  }

  depends_on = [
    google_project_service.services,
    google_bigquery_dataset.dataset,
  ]
}
