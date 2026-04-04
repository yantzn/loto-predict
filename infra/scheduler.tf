resource "google_cloud_scheduler_job" "fetch_loto6_job" {
  name      = "fetch-loto6-job"
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
    google_cloud_run_service_iam_member.fetch_scheduler_invoker,
    google_service_account_iam_member.scheduler_service_agent_token_creator,
  ]
}

resource "google_cloud_scheduler_job" "fetch_loto7_job" {
  name      = "fetch-loto7-job"
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
    google_cloud_run_service_iam_member.fetch_scheduler_invoker,
    google_service_account_iam_member.scheduler_service_agent_token_creator,
  ]
}

resource "google_cloud_scheduler_job" "notify_loto6_job" {
  name      = "notify-loto6-job"
  region    = var.region
  schedule  = var.notify_loto6_cron
  time_zone = var.scheduler_time_zone

  http_target {
    uri         = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      lottery_type        = "LOTO6"
      history_limit_loto6 = var.history_limit_loto6
    }))

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.generate_prediction_and_notify,
    google_cloud_run_service_iam_member.notify_scheduler_invoker,
    google_service_account_iam_member.scheduler_service_agent_token_creator,
  ]
}

resource "google_cloud_scheduler_job" "notify_loto7_job" {
  name      = "notify-loto7-job"
  region    = var.region
  schedule  = var.notify_loto7_cron
  time_zone = var.scheduler_time_zone

  http_target {
    uri         = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      lottery_type        = "LOTO7"
      history_limit_loto7 = var.history_limit_loto7
    }))

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.generate_prediction_and_notify,
    google_cloud_run_service_iam_member.notify_scheduler_invoker,
    google_service_account_iam_member.scheduler_service_agent_token_creator,
  ]
}
