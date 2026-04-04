resource "google_cloudfunctions2_function" "loto_orchestrator" {
  name     = var.function_name
  location = var.region

  build_config {
    runtime     = var.runtime
    entry_point = "entry_point"

    source {
      storage_source {
        bucket = var.source_bucket_name
        object = var.source_object_name
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
      APP_ENV            = var.app_env
      APP_TIMEZONE       = var.app_timezone
      GCP_PROJECT_ID     = var.project_id
      GCP_REGION         = var.region
      BIGQUERY_DATASET   = var.dataset_id
      LOG_LEVEL          = var.log_level
      LOG_JSON           = var.log_json
      SERVICE_NAME       = var.service_name
      STATS_TARGET_DRAWS = tostring(var.stats_target_draws)
      PREDICTION_COUNT   = tostring(var.prediction_count)
      LOTO6_NUMBER_MIN   = tostring(var.loto6_number_min)
      LOTO6_NUMBER_MAX   = tostring(var.loto6_number_max)
      LOTO6_PICK_COUNT   = tostring(var.loto6_pick_count)
      LOTO7_NUMBER_MIN   = tostring(var.loto7_number_min)
      LOTO7_NUMBER_MAX   = tostring(var.loto7_number_max)
      LOTO7_PICK_COUNT   = tostring(var.loto7_pick_count)
    }

    secret_environment_variables {
      key        = "LINE_CHANNEL_ACCESS_TOKEN"
      project_id = var.project_id
      secret     = google_secret_manager_secret.line_channel_access_token.secret_id
      version    = "latest"
    }

    secret_environment_variables {
      key        = "LINE_USER_ID"
      project_id = var.project_id
      secret     = google_secret_manager_secret.line_user_id.secret_id
      version    = "latest"
    }
  }
}
