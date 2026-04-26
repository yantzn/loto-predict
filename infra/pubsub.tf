resource "google_pubsub_topic" "import_requests" {
  name    = "import-loto-results"
  project = var.project_id
  labels  = local.common_labels

  depends_on = [
    google_project_service.services,
  ]
}

resource "google_pubsub_topic" "notify_requests" {
  name    = "notify-loto-prediction"
  project = var.project_id
  labels  = local.common_labels

  depends_on = [
    google_project_service.services,
  ]
}
