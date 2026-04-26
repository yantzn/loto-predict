resource "google_cloud_run_v2_job" "backfill_loto_history" {
  name     = local.backfill_job_name
  location = var.region
  project  = var.project_id

  labels = local.common_labels

  template {
    template {
      service_account = var.cloud_run_jobs_service_account_email
      timeout         = "${var.backfill_job_timeout_seconds}s"
      max_retries     = 1

      containers {
        # このJobは backfill ソースからビルドされたイメージを実行する。
        # deploy-backfill-job-source.yml と同じエントリポイント(main.py)に揃えて
        # Terraform 再適用時の起動失敗を防ぐ。
        image = var.backfill_job_image

        # 必須引数をTerraformで明示的に渡して、実ジョブとしてそのまま実行可能にする。
        # Buildpack イメージでは launcher 経由で実行して Python ランタイム環境を有効化する。
        # 手動実行時は gcloud run jobs execute --args で上書きしやすい構成。
        command = ["/cnb/lifecycle/launcher"]
        args = [
          "python",
          "main.py",
          "--lottery-type", var.backfill_default_lottery_type,
          "--start-date", var.backfill_default_start_date,
          "--end-date", var.backfill_default_end_date,
          "--output-path", var.backfill_default_output_path != "" ? var.backfill_default_output_path : "gs://${google_storage_bucket.raw_bucket.name}/backfill/default.csv",
        ]

        env {
          name  = "APP_ENV"
          value = "gcp"
        }

        env {
          name  = "APP_TIMEZONE"
          value = var.app_timezone
        }

        env {
          name  = "LOG_LEVEL"
          value = var.log_level
        }

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "GCP_REGION"
          value = var.region
        }

        env {
          name  = "BQ_DATASET"
          value = google_bigquery_dataset.dataset.dataset_id
        }

        env {
          name  = "GCS_BUCKET_RAW"
          value = google_storage_bucket.raw_bucket.name
        }

        env {
          name  = "BQ_TABLE_LOTO6_HISTORY"
          value = google_bigquery_table.loto6_history.table_id
        }

        env {
          name  = "BQ_TABLE_LOTO7_HISTORY"
          value = google_bigquery_table.loto7_history.table_id
        }

        env {
          name  = "BQ_TABLE_PREDICTION_RUNS"
          value = google_bigquery_table.prediction_runs.table_id
        }

        resources {
          limits = {
            cpu    = var.backfill_job_cpu
            memory = var.backfill_job_memory
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }

  depends_on = [
    google_project_service.services,
    google_storage_bucket.raw_bucket,
    google_bigquery_dataset.dataset,
    google_bigquery_table.loto6_history,
    google_bigquery_table.loto7_history,
    google_bigquery_table.prediction_runs,
  ]
}
