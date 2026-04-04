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

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "raw_bucket_name" {
  description = "Bucket name for scraped/manual CSV files. If null, use ${project_id}-loto-raw."
  type        = string
  default     = null
}

variable "source_bucket_name" {
  description = "Bucket name that stores Cloud Functions source zip files"
  type        = string
}

variable "fetch_function_source_object" {
  description = "GCS object path for fetch_loto_results source zip"
  type        = string
}

variable "import_function_source_object" {
  description = "GCS object path for import_loto_results_to_bq source zip"
  type        = string
}

variable "notify_function_source_object" {
  description = "GCS object path for generate_prediction_and_notify source zip"
  type        = string
}

variable "functions_runtime_service_account_email" {
  description = "Service account email used by Cloud Functions runtime"
  type        = string
}

variable "scheduler_invoker_service_account_email" {
  description = "Service account email used by Cloud Scheduler OIDC invocations"
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
  description = "Existing Secret Manager secret id for LINE channel access token"
  type        = string
}

variable "line_user_id_secret_id" {
  description = "Existing Secret Manager secret id for LINE target user id"
  type        = string
}

locals {
  resolved_raw_bucket_name = coalesce(var.raw_bucket_name, "${var.project_id}-loto-raw")
}
