resource "google_bigquery_dataset" "dataset" {
  dataset_id = var.dataset_id
  location   = var.region

  labels = local.common_labels

  depends_on = [google_project_service.services]
}

resource "google_bigquery_table" "loto6_draw_results" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = "loto6_draw_results"
  schema     = file("${path.module}/schemas/loto6_draw_results.json")

  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }

  clustering = ["draw_no"]
}

resource "google_bigquery_table" "loto7_draw_results" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = "loto7_draw_results"
  schema     = file("${path.module}/schemas/loto7_draw_results.json")

  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }

  clustering = ["draw_no"]
}

resource "google_bigquery_table" "prediction_runs" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = "prediction_runs"
  schema     = file("${path.module}/schemas/prediction_runs.json")

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["lottery_type"]
}

resource "google_bigquery_table" "execution_logs" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = "execution_logs"
  schema     = file("${path.module}/schemas/execution_logs.json")

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["function_name", "status"]
}
