resource "google_secret_manager_secret" "line_channel_access_token" {
  secret_id = var.line_channel_access_token_secret_id

  replication {
    auto {}
  }

  depends_on = [
    google_project_service.services
  ]
}

resource "google_secret_manager_secret_version" "line_channel_access_token" {
  secret      = google_secret_manager_secret.line_channel_access_token.id
  secret_data = var.line_channel_access_token
}

resource "google_secret_manager_secret" "line_user_id" {
  secret_id = var.line_user_id_secret_id

  replication {
    auto {}
  }

  depends_on = [
    google_project_service.services
  ]
}

resource "google_secret_manager_secret_version" "line_user_id" {
  secret      = google_secret_manager_secret.line_user_id.id
  secret_data = var.line_to_user_id
}
