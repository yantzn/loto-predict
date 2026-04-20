resource "google_artifact_registry_repository" "loto_predict" {
  project       = var.project_id
  location      = var.region
  repository_id = "loto-predict"
  format        = "DOCKER"
  description   = "Container repository for loto-predict workloads"

  depends_on = [
    google_project_service.services,
  ]
}
