resource "random_id" "bucket_suffix" {
  byte_length = 3

  keepers = {
    project_id = var.project_id
    region     = var.region
    rotation   = var.bucket_rotation_key
  }
}

locals {
  generated_raw_bucket_name = "${var.project_id}-loto-raw-${random_id.bucket_suffix.hex}"

  resolved_raw_bucket_name = coalesce(
    var.raw_bucket_name,
    local.generated_raw_bucket_name
  )
}

resource "google_storage_bucket" "raw_bucket" {
  name                        = local.resolved_raw_bucket_name
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = false

  labels = local.common_labels

  lifecycle_rule {
    action {
      type = "Delete"
    }

    condition {
      age = 30
    }
  }

  depends_on = [
    google_project_service.services,
  ]
}
