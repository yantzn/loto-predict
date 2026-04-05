resource "google_pubsub_topic" "import_requests" {
  name    = "import-loto-results"
  project = var.project_id

  labels = local.common_labels

  depends_on = [
    google_project_service.services,
  ]
}

resource "google_pubsub_topic" "notify_requests" {
  name    = "notify-loto-prediction"
  project = var.project_id

  labels = local.common_labels

  depends_on = [
    google_project_service.services,
  ]
}

resource "google_pubsub_subscription" "import_requests_push" {
  name    = "import-loto-results-push"
  project = var.project_id
  topic   = google_pubsub_topic.import_requests.id

  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"

  push_config {
    push_endpoint = google_cloudfunctions2_function.import_loto_results_to_bq.service_config[0].uri

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.import_loto_results_to_bq.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.import_loto_results_to_bq,
    google_cloud_run_service_iam_member.import_pubsub_invoker,
    google_service_account_iam_member.pubsub_service_agent_token_creator,
  ]
}

resource "google_pubsub_subscription" "notify_requests_push" {
  name    = "notify-loto-prediction-push"
  project = var.project_id
  topic   = google_pubsub_topic.notify_requests.id

  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"

  push_config {
    push_endpoint = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri

    oidc_token {
      service_account_email = var.scheduler_invoker_service_account_email
      audience              = google_cloudfunctions2_function.generate_prediction_and_notify.service_config[0].uri
    }
  }

  depends_on = [
    google_cloudfunctions2_function.generate_prediction_and_notify,
    google_cloud_run_service_iam_member.notify_pubsub_invoker,
    google_service_account_iam_member.pubsub_service_agent_token_creator,
  ]
}
