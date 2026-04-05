locals {
  common_labels = {
    system     = "loto-predict"
    managed_by = "terraform"
    module     = "infra"
  }

  table_ids = {
    loto6_history   = "loto6_history"
    loto7_history   = "loto7_history"
    prediction_runs = "prediction_runs"
    execution_logs  = "execution_logs"
  }
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "random_id" "raw_bucket_suffix" {
  byte_length = 3

  keepers = {
    rotation = var.bucket_rotation_key
    project  = var.project_id
    region   = var.region
  }
}

locals {
  effective_raw_bucket_name = coalesce(
    var.raw_bucket_name,
    "${var.project_id}-raw-${random_id.raw_bucket_suffix.hex}"
  )
}

resource "google_project_service" "services" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com"
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "raw" {
  name                        = local.effective_raw_bucket_name
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = false
  labels                      = local.common_labels

  depends_on = [google_project_service.services]
}

resource "google_bigquery_dataset" "dataset" {
  project    = var.project_id
  dataset_id = var.dataset_id
  location   = var.region
  labels     = local.common_labels

  delete_contents_on_destroy = false

  depends_on = [google_project_service.services]
}

resource "google_bigquery_table" "loto6_history" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.loto6_history
  labels     = local.common_labels

  deletion_protection = false

  schema = jsonencode([
    { name = "draw_no", type = "INTEGER", mode = "REQUIRED" },
    { name = "draw_date", type = "DATE", mode = "REQUIRED" },
    { name = "number1", type = "INTEGER", mode = "REQUIRED" },
    { name = "number2", type = "INTEGER", mode = "REQUIRED" },
    { name = "number3", type = "INTEGER", mode = "REQUIRED" },
    { name = "number4", type = "INTEGER", mode = "REQUIRED" },
    { name = "number5", type = "INTEGER", mode = "REQUIRED" },
    { name = "number6", type = "INTEGER", mode = "REQUIRED" },
    { name = "bonus_number", type = "INTEGER", mode = "NULLABLE" },
    { name = "source_file_name", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])

  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }
}

resource "google_bigquery_table" "loto7_history" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.loto7_history
  labels     = local.common_labels

  deletion_protection = false

  schema = jsonencode([
    { name = "draw_no", type = "INTEGER", mode = "REQUIRED" },
    { name = "draw_date", type = "DATE", mode = "REQUIRED" },
    { name = "number1", type = "INTEGER", mode = "REQUIRED" },
    { name = "number2", type = "INTEGER", mode = "REQUIRED" },
    { name = "number3", type = "INTEGER", mode = "REQUIRED" },
    { name = "number4", type = "INTEGER", mode = "REQUIRED" },
    { name = "number5", type = "INTEGER", mode = "REQUIRED" },
    { name = "number6", type = "INTEGER", mode = "REQUIRED" },
    { name = "number7", type = "INTEGER", mode = "REQUIRED" },
    { name = "bonus_number1", type = "INTEGER", mode = "NULLABLE" },
    { name = "bonus_number2", type = "INTEGER", mode = "NULLABLE" },
    { name = "source_file_name", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])

  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }
}

resource "google_bigquery_table" "prediction_runs" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.prediction_runs
  labels     = local.common_labels

  deletion_protection = false

  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "lottery_type", type = "STRING", mode = "REQUIRED" },
    { name = "prediction_numbers", type = "STRING", mode = "REQUIRED" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "created_date", type = "DATE", mode = "REQUIRED" }
  ])

  time_partitioning {
    type  = "DAY"
    field = "created_date"
  }
}

resource "google_bigquery_table" "execution_logs" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.execution_logs
  labels     = local.common_labels

  deletion_protection = false

  schema = jsonencode([
    { name = "execution_id", type = "STRING", mode = "REQUIRED" },
    { name = "function_name", type = "STRING", mode = "REQUIRED" },
    { name = "lottery_type", type = "STRING", mode = "NULLABLE" },
    { name = "stage", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "message", type = "STRING", mode = "NULLABLE" },
    { name = "gcs_bucket", type = "STRING", mode = "NULLABLE" },
    { name = "gcs_object", type = "STRING", mode = "NULLABLE" },
    { name = "draw_no", type = "INTEGER", mode = "NULLABLE" },
    { name = "run_id", type = "STRING", mode = "NULLABLE" },
    { name = "error_type", type = "STRING", mode = "NULLABLE" },
    { name = "error_detail", type = "STRING", mode = "NULLABLE" },
    { name = "executed_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "executed_date", type = "DATE", mode = "REQUIRED" }
  ])

  time_partitioning {
    type  = "DAY"
    field = "executed_date"
  }
}

resource "google_bigquery_dataset_iam_member" "functions_runtime_bigquery_data_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_project_iam_member" "functions_runtime_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_project_iam_member" "functions_runtime_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
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

resource "google_storage_bucket_iam_member" "functions_runtime_raw_bucket_admin" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.functions_runtime_service_account_email}"
}

resource "google_pubsub_topic" "import_requests" {
  name    = "import-loto-results"
  project = var.project_id
  labels  = local.common_labels

  depends_on = [google_project_service.services]
}

resource "google_pubsub_topic" "notify_requests" {
  name    = "notify-loto-prediction"
  project = var.project_id
  labels  = local.common_labels

  depends_on = [google_project_service.services]
}

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
    available_memory               = var.function_available_memory
    timeout_seconds                = var.function_timeout_seconds
    min_instance_count             = var.function_min_instance_count
    max_instance_count             = var.function_max_instance_count
    ingress_settings               = "ALLOW_ALL"
    all_traffic_on_latest_revision = true
    service_account_email          = var.functions_runtime_service_account_email

    environment_variables = {
      GCP_PROJECT_ID          = var.project_id
      GCP_REGION              = var.region
      BIGQUERY_DATASET        = var.dataset_id
      BQ_TABLE_EXECUTION_LOGS = local.table_ids.execution_logs
      RAW_BUCKET_NAME         = google_storage_bucket.raw.name
      IMPORT_TOPIC_NAME       = google_pubsub_topic.import_requests.name
      APP_TIMEZONE            = var.app_timezone
      LOG_LEVEL               = var.log_level
    }
  }

  depends_on = [
    google_project_service.services,
    google_storage_bucket.raw,
    google_pubsub_topic.import_requests,
    google_bigquery_dataset.dataset
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
    available_memory               = var.function_available_memory
    timeout_seconds                = 300
    min_instance_count             = var.function_min_instance_count
    max_instance_count             = var.function_max_instance_count
    ingress_settings               = "ALLOW_ALL"
    all_traffic_on_latest_revision = true
    service_account_email          = var.functions_runtime_service_account_email

    environment_variables = {
      GCP_PROJECT_ID          = var.project_id
      GCP_REGION              = var.region
      BIGQUERY_DATASET        = var.dataset_id
      BQ_TABLE_LOTO6_HISTORY  = local.table_ids.loto6_history
      BQ_TABLE_LOTO7_HISTORY  = local.table_ids.loto7_history
      BQ_TABLE_EXECUTION_LOGS = local.table_ids.execution_logs
      NOTIFY_TOPIC_NAME       = google_pubsub_topic.notify_requests.name
      APP_TIMEZONE            = var.app_timezone
      LOG_LEVEL               = var.log_level
    }
  }

  depends_on = [
    google_project_service.services,
    google_bigquery_dataset.dataset,
    google_pubsub_topic.notify_requests
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
    available_memory               = var.function_available_memory
    timeout_seconds                = var.function_timeout_seconds
    min_instance_count             = var.function_min_instance_count
    max_instance_count             = var.function_max_instance_count
    ingress_settings               = "ALLOW_ALL"
    all_traffic_on_latest_revision = true
    service_account_email          = var.functions_runtime_service_account_email

    environment_variables = {
      APP_TIMEZONE             = var.app_timezone
      GCP_PROJECT_ID           = var.project_id
      GCP_REGION               = var.region
      BIGQUERY_DATASET         = var.dataset_id
      BQ_TABLE_LOTO6_HISTORY   = local.table_ids.loto6_history
      BQ_TABLE_LOTO7_HISTORY   = local.table_ids.loto7_history
      BQ_TABLE_PREDICTION_RUNS = local.table_ids.prediction_runs
      BQ_TABLE_EXECUTION_LOGS  = local.table_ids.execution_logs
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
    google_bigquery_dataset.dataset
  ]
}

resource "google_cloud_run_service_iam_member" "fetch_scheduler_invoker" {
  location = var.region
  project  = var.project_id
  service  = google_cloudfunctions2_function.fetch_loto_results.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.scheduler_invoker_service_account_email}"
}

resource "google_cloud_run_service_iam_member" "import_pubsub_invoker" {
  location = var.region
  project  = var.project_id
  service  = google_cloudfunctions2_function.import_loto_results_to_bq.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.scheduler_invoker_service_account_email}"
}

resource "google_cloud_run_service_iam_member" "notify_pubsub_invoker" {
  location = var.region
  project  = var.project_id
  service  = google_cloudfunctions2_function.generate_prediction_and_notify.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.scheduler_invoker_service_account_email}"
}

resource "google_pubsub_subscription" "import_requests_push" {
  name    = "import-loto-results-push"
  project = var.project_id
  topic   = google_pubsub_topic.import_requests.id

  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"

  push_config {
    push_endpoint = google_cloudfunctions2_function.import_loto_results_to_bq.service_config[0].uri

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.import_loto_results_to_bq.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.import_loto_results_to_bq,
    google_cloud_run_service_iam_member.import_pubsub_invoker
  ]
}

resource "google_pubsub_subscription" "notify_requests_push" {
  name    = "notify-loto-prediction-push"
  project = var.project_id
  topic   = google_pubsub_topic.notify_requests.id

  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"

  push_config {
    push_endpoint = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.generate_prediction_and_notify,
    google_cloud_run_service_iam_member.notify_pubsub_invoker
  ]
}

resource "google_cloud_scheduler_job" "fetch_loto6_job" {
  name      = "fetch-loto6-job"
  project   = var.project_id
  region    = var.region
  schedule  = var.fetch_loto6_cron
  time_zone = var.scheduler_time_zone

  http_target {
    uri         = google_cloudfunctions2_function.fetch_loto_results.service_config[0].uri
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      lottery_type = "LOTO6"
    }))

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.fetch_loto_results.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.fetch_loto_results,
    google_cloud_run_service_iam_member.fetch_scheduler_invoker
  ]
}

resource "google_cloud_scheduler_job" "fetch_loto7_job" {
  name      = "fetch-loto7-job"
  project   = var.project_id
  region    = var.region
  schedule  = var.fetch_loto7_cron
  time_zone = var.scheduler_time_zone

  http_target {
    uri         = google_cloudfunctions2_function.fetch_loto_results.service_config[0].uri
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      lottery_type = "LOTO7"
    }))

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.fetch_loto_results.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.fetch_loto_results,
    google_cloud_run_service_iam_member.fetch_scheduler_invoker
  ]
}
