resource "google_bigquery_dataset" "dataset" {
  dataset_id = var.dataset_id
  location   = var.region
  labels     = local.common_labels

  depends_on = [
    google_project_service.services
  ]
}

resource "google_bigquery_table" "loto6_history" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.loto6_history
  schema     = file("${path.module}/schemas/loto6_draw_results.json")

  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }

  clustering = ["draw_number"]
}

resource "google_bigquery_table" "loto7_history" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.loto7_history
  schema     = file("${path.module}/schemas/loto7_draw_results.json")

  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }

  clustering = ["draw_number"]
}

resource "google_bigquery_table" "loto6_history_staging" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.loto6_history_staging
  schema     = file("${path.module}/schemas/loto6_draw_results.json")
}

resource "google_bigquery_table" "loto7_history_staging" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.loto7_history_staging
  schema     = file("${path.module}/schemas/loto7_draw_results.json")
}

resource "google_bigquery_table" "prediction_runs" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.prediction_runs
  schema     = file("${path.module}/schemas/prediction_runs.json")

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["lottery_type"]
}

resource "google_bigquery_table" "execution_logs" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = local.table_ids.execution_logs
  schema     = file("${path.module}/schemas/execution_logs.json")

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["function_name", "status"]
}
