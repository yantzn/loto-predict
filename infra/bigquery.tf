resource "google_bigquery_dataset" "dataset" {
  project                    = var.project_id
  dataset_id                 = var.dataset_id
  location                   = var.region
  delete_contents_on_destroy = false

  labels = local.common_labels

  depends_on = [
    google_project_service.services,
  ]
}

resource "google_bigquery_table" "loto6_history" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.dataset.dataset_id
  table_id            = local.table_ids.loto6_history
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }

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
}

resource "google_bigquery_table" "loto7_history" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.dataset.dataset_id
  table_id            = local.table_ids.loto7_history
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }

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
}

resource "google_bigquery_table" "loto6_validation_stage" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.dataset.dataset_id
  table_id            = local.table_ids.loto6_validation_stage
  deletion_protection = false

  schema = google_bigquery_table.loto6_history.schema
}

resource "google_bigquery_table" "loto7_validation_stage" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.dataset.dataset_id
  table_id            = local.table_ids.loto7_validation_stage
  deletion_protection = false

  schema = google_bigquery_table.loto7_history.schema
}

resource "google_bigquery_table" "prediction_runs" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.dataset.dataset_id
  table_id            = local.table_ids.prediction_runs
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "created_date"
  }

  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "lottery_type", type = "STRING", mode = "REQUIRED" },
    { name = "prediction_numbers", type = "STRING", mode = "REQUIRED" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "created_date", type = "DATE", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "execution_logs" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = "execution_logs"
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
