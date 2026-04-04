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
