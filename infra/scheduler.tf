resource "google_cloud_scheduler_job" "fetch_loto6_job" {
  name      = "fetch-loto6-job"
  region    = var.region
  schedule  = "5 19 * * 1,4"
  time_zone = var.scheduler_time_zone
  http_target {
    uri         = google_cloudfunctions2_function.fetch_loto_results.service_config[0].uri
    http_method = "POST"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode(jsonencode({ lottery_type = "loto6" }))
    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.fetch_loto_results.service_config[0].uri
    }
  }
}

resource "google_cloud_scheduler_job" "fetch_loto7_job" {
  name      = "fetch-loto7-job"
  region    = var.region
  schedule  = "5 19 * * 5"
  time_zone = var.scheduler_time_zone
  http_target {
    uri         = google_cloudfunctions2_function.fetch_loto_results.service_config[0].uri
    http_method = "POST"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode(jsonencode({ lottery_type = "loto7" }))
    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.fetch_loto_results.service_config[0].uri
    }
  }
}

resource "google_cloud_scheduler_job" "notify_loto6_job" {
  name      = "notify-loto6-job"
  region    = var.region
  schedule  = "10 19 * * 1,4"
  time_zone = var.scheduler_time_zone
  http_target {
    uri         = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    http_method = "POST"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode(jsonencode({ lottery_type = "loto6" }))
    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    }
  }
}

resource "google_cloud_scheduler_job" "notify_loto7_job" {
  name      = "notify-loto7-job"
  region    = var.region
  schedule  = "10 19 * * 5"
  time_zone = var.scheduler_time_zone
  http_target {
    uri         = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    http_method = "POST"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode(jsonencode({ lottery_type = "loto7" }))
    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    }
  }
}
resource "google_cloud_scheduler_job" "loto6_sync_job" {
  name      = "loto6-sync-job"
  region    = var.region
  schedule  = "0 19 * * 1,4"
  time_zone = var.scheduler_time_zone

  http_target {
    uri         = google_cloudfunctions2_function.loto_sync.service_config[0].uri
    http_method = "POST"
    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      lottery_type = "LOTO6"
    }))

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.loto_sync.service_config[0].uri
    }
  }
}

resource "google_cloud_scheduler_job" "loto7_sync_job" {
  name      = "loto7-sync-job"
  region    = var.region
  schedule  = "0 19 * * 5"
  time_zone = var.scheduler_time_zone

  http_target {
    uri         = google_cloudfunctions2_function.loto_sync.service_config[0].uri
    http_method = "POST"
    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      lottery_type = "LOTO7"
    }))

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.loto_sync.service_config[0].uri
    }
  }
}

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
}
