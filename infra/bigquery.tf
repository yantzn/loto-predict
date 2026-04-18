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

  # history テーブルは generate_prediction_and_notify の元データ。
  # import 処理と repository が同じ n1..n7, b1..b2 形式を参照する。
  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }

  clustering = ["draw_no"]

  schema = file("${path.module}/schemas/loto6_results.json")
}

resource "google_bigquery_table" "loto7_history" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.dataset.dataset_id
  table_id            = local.table_ids.loto7_history
  deletion_protection = false

  # history テーブルは generate_prediction_and_notify の元データ。
  # import 処理と repository が同じ n1..n7, b1..b2 形式を参照する。
  time_partitioning {
    type  = "DAY"
    field = "draw_date"
  }

  clustering = ["draw_no"]

  schema = file("${path.module}/schemas/loto7_results.json")
}

resource "google_bigquery_table" "prediction_runs" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.dataset.dataset_id
  table_id            = local.table_ids.prediction_runs
  deletion_protection = false

  # prediction_runs は通知した予想の監査テーブル。
  # repository.save_prediction_run() 側で「1口=1行」に展開して保存する。
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["execution_id", "draw_no"]

  schema = file("${path.module}/schemas/prediction_runs.json")
}

resource "google_bigquery_table" "execution_logs" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = "execution_logs"
  labels     = local.common_labels

  deletion_protection = false

  # execution_logs は Cloud Functions 実行ログ用途。
  # prediction_runs で保持しない失敗監査情報はこのテーブルで追跡する。
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
