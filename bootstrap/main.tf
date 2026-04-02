locals {
  repository_name_sanitized = replace(replace(var.github_repository, "/", "-"), "_", "-")

  common_labels = {
    system     = "loto-predict-line"
    managed_by = "terraform"
    module     = "bootstrap"
    repository = local.repository_name_sanitized
  }
}

resource "random_id" "suffix" {
  byte_length = 3

  keepers = {
    project_id   = var.project_id
    rotation_key = var.rotation_key
  }
}

locals {
  suffix = random_id.suffix.hex

  tfstate_bucket_name = "${var.project_id}-tfstate-${local.suffix}"

  github_actions_sa_account_id = "gha-loto-${local.suffix}"
  functions_runtime_account_id = "loto-fn-runtime-${local.suffix}"
  workflow_runner_account_id   = "loto-workflow-runner-${local.suffix}"
  scheduler_invoker_account_id = "loto-scheduler-invoker-${local.suffix}"
}

#
# APIs commonly needed by bootstrap and downstream infra
#
resource "google_project_service" "services" {
  for_each = toset([
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudfunctions.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "cloudscheduler.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

#
# Terraform backend bucket
#
resource "google_storage_bucket" "tfstate" {
  name                        = local.tfstate_bucket_name
  location                    = var.tfstate_location
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  labels = local.common_labels

  depends_on = [google_project_service.services]
}

#
# Service Accounts
#
resource "google_service_account" "github_actions" {
  account_id   = local.github_actions_sa_account_id
  display_name = "GitHub Actions deployer for loto-predict-line"

  depends_on = [google_project_service.services]
}

resource "google_service_account" "functions_runtime" {
  account_id   = local.functions_runtime_account_id
  display_name = "Cloud Functions runtime for loto-predict-line"

  depends_on = [google_project_service.services]
}

resource "google_service_account" "workflow_runner" {
  account_id   = local.workflow_runner_account_id
  display_name = "Workflow runner for loto-predict-line"

  depends_on = [google_project_service.services]
}

resource "google_service_account" "scheduler_invoker" {
  account_id   = local.scheduler_invoker_account_id
  display_name = "Cloud Scheduler invoker for loto-predict-line"

  depends_on = [google_project_service.services]
}

#
# Give GitHub Actions SA enough rights to manage downstream infra.
# Tighten further later if you want; this is intentionally focused on infra deployment.
#
resource "google_project_iam_member" "github_actions_roles" {
  for_each = toset([
    "roles/storage.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/cloudfunctions.admin",
    "roles/run.admin",
    "roles/cloudbuild.builds.editor",
    "roles/artifactregistry.admin",
    "roles/bigquery.admin",
    "roles/secretmanager.admin",
    "roles/cloudscheduler.admin",
    "roles/logging.configWriter",
    "roles/resourcemanager.projectIamAdmin",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

#
# Runtime SA baseline roles
#
resource "google_project_iam_member" "functions_runtime_roles" {
  for_each = toset([
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.functions_runtime.email}"
}

#
# Workflow runner SA baseline roles (kept separate for future expansion)
#
resource "google_project_iam_member" "workflow_runner_roles" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/bigquery.jobUser",
    "roles/bigquery.dataViewer",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.workflow_runner.email}"
}

#
# Scheduler invoker SA baseline:
# run.invoker is bound later at service level by infra,
# but token creation support is useful.
#
resource "google_project_iam_member" "scheduler_invoker_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}

#
# Workload Identity Pool / Provider for GitHub Actions OIDC
#
resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = var.wif_pool_id
  display_name              = "GitHub Actions Pool"
  description               = "OIDC pool for GitHub Actions"

  depends_on = [google_project_service.services]
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = var.wif_provider_id
  display_name                       = "GitHub Actions Provider"
  description                        = "OIDC provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.aud"        = "assertion.aud"
    "attribute.repository" = "assertion.repository"
    "attribute.owner"      = "assertion.repository_owner"
    "attribute.ref"        = "assertion.ref"
  }

  # 連携先 GitHub リポジトリを固定（最重要）。
  # フォークや別repoからのトークンを拒否するための境界。
  attribute_condition = "assertion.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

#
# Allow the specific GitHub repository to impersonate the GitHub Actions SA
#
resource "google_service_account_iam_member" "github_actions_wif_user" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repository}"
}
