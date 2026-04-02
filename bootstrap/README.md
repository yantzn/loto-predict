output "tfstate_bucket_name" {
  description = "Terraform backend bucket name for downstream infra"
  value       = google_storage_bucket.tfstate.name
}

output "source_bucket_name" {
  description = "Bucket name for Cloud Function source archives"
  value       = google_storage_bucket.source.name
}

output "workload_identity_provider_name" {
  description = "Full Workload Identity Provider resource name"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "github_actions_service_account_email" {
  description = "GitHub Actions deployer SA email"
  value       = google_service_account.github_actions.email
}

output "functions_runtime_service_account_email" {
  description = "Cloud Functions runtime SA email"
  value       = google_service_account.functions_runtime.email
}

output "workflow_runner_service_account_email" {
  description = "Workflow runner SA email"
  value       = google_service_account.workflow_runner.email
}

output "scheduler_invoker_service_account_email" {
  description = "Cloud Scheduler invoker SA email"
  value       = google_service_account.scheduler_invoker.email
}
