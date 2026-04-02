resource "google_cloud_scheduler_job" "loto6_job" {
  name      = "loto6-predict-job"
  region    = var.region
  schedule  = var.scheduler_loto6_cron
  time_zone = var.scheduler_time_zone

  http_target {
    uri         = google_cloudfunctions2_function.loto_orchestrator.service_config[0].uri
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      lottery_type       = "LOTO6"
      prediction_count   = var.prediction_count
      stats_target_draws = var.stats_target_draws
    }))

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.loto_orchestrator.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.loto_orchestrator,
    google_cloud_run_service_iam_member.scheduler_invoker,
  ]
}

resource "google_cloud_scheduler_job" "loto7_job" {
  name      = "loto7-predict-job"
  region    = var.region
  schedule  = var.scheduler_loto7_cron
  time_zone = var.scheduler_time_zone

  http_target {
    uri         = google_cloudfunctions2_function.loto_orchestrator.service_config[0].uri
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      lottery_type       = "LOTO7"
      prediction_count   = var.prediction_count
      stats_target_draws = var.stats_target_draws
    }))

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.loto_orchestrator.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.loto_orchestrator,
    google_cloud_run_service_iam_member.scheduler_invoker,
  ]
}
