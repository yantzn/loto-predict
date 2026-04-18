resource "google_cloud_run_v2_job" "backfill_loto_history" {
  name     = local.backfill_job_name
  location = var.region
  project  = var.project_id

  labels = local.common_labels

  deletion_protection = false

  template {
    template {
      service_account = var.cloud_run_jobs_service_account_email
      timeout         = "${var.backfill_job_timeout_seconds}s"
      max_retries     = 1

      containers {
        image = "us-docker.pkg.dev/cloudrun/container/job:latest"

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
