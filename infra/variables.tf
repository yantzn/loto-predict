variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-northeast1"
}

variable "app_timezone" {
  description = "Application timezone"
  type        = string
  default     = "Asia/Tokyo"
}

variable "dataset_id" {
  description = "BigQuery dataset ID"
  type        = string
  default     = "loto_predict"
}

variable "runtime" {
  description = "Cloud Functions runtime"
  type        = string
  default     = "python312"
}

variable "function_timeout_seconds" {
  description = "Default timeout for Cloud Functions"
  type        = number
  default     = 120
}

variable "function_available_memory" {
  description = "Default memory for Cloud Functions"
  type        = string
  default     = "512M"
}

variable "function_min_instance_count" {
  description = "Minimum instance count for Cloud Functions"
  type        = number
  default     = 0
}

variable "function_max_instance_count" {
  description = "Maximum instance count for Cloud Functions"
  type        = number
  default     = 1
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "source_bucket_name" {
  description = "Bucket name that stores Cloud Functions source packages"
  type        = string
}

variable "functions_runtime_service_account_email" {
  description = "Service account email used by Cloud Functions runtime"
  type        = string
}

variable "scheduler_invoker_service_account_email" {
  description = "Service account email used by Cloud Scheduler and Pub/Sub push OIDC invocations"
  type        = string
}

variable "cloud_run_jobs_service_account_email" {
  description = "Service account email used by Cloud Run Jobs"
  type        = string
}

variable "history_limit_loto6" {
  description = "History window size used when generating loto6 predictions"
  type        = number
  default     = 100
}

variable "history_limit_loto7" {
  description = "History window size used when generating loto7 predictions"
  type        = number
  default     = 100
}

variable "line_channel_access_token_secret_id" {
  description = "Existing Secret Manager secret ID for LINE channel access token"
  type        = string
}

variable "line_channel_access_token_secret_version" {
  description = "Secret version for LINE channel access token"
  type        = string
  default     = "1"
}

variable "line_user_id_secret_id" {
  description = "Existing Secret Manager secret ID for LINE target user ID"
  type        = string
}

variable "line_user_id_secret_version" {
  description = "Secret version for LINE target user ID"
  type        = string
  default     = "1"
}

variable "scheduler_time_zone" {
  description = "Time zone used by Cloud Scheduler"
  type        = string
  default     = "Asia/Tokyo"
}

variable "fetch_loto6_cron" {
  description = "Cron expression for LOTO6 fetch job"
  type        = string
  default     = "5 19 * * 1,4"
}

variable "fetch_loto7_cron" {
  description = "Cron expression for LOTO7 fetch job"
  type        = string
  default     = "5 19 * * 5"
}

variable "raw_bucket_name" {
  description = "Raw bucket name. If null, Terraform generates one with suffix."
  type        = string
  default     = null
}

variable "bucket_rotation_key" {
  description = "Change only when intentionally rotating generated bucket names."
  type        = string
  default     = "v1"
}

variable "backfill_job_timeout_seconds" {
  description = "Timeout for a single Cloud Run Job task"
  type        = number
  default     = 3600
}

variable "backfill_job_memory" {
  description = "Memory for Cloud Run Job"
  type        = string
  default     = "1Gi"
}

variable "backfill_job_cpu" {
  description = "CPU for Cloud Run Job"
  type        = string
  default     = "1"
}
