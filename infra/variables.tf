variable "project_id" {
  type        = string
  description = "GCP project id"
}

variable "region" {
  type        = string
  description = "Default region"
  default     = "asia-northeast1"
}

variable "dataset_id" {
  type        = string
  description = "BigQuery dataset id"
  default     = "loto_predict"
}

variable "function_name" {
  type        = string
  description = "Cloud Function name"
  default     = "loto-orchestrator"
}

variable "runtime" {
  type        = string
  description = "Python runtime version"
  default     = "python312"
}

variable "source_bucket_name" {
  type        = string
  description = "Bucket for function source archives"
}

variable "source_object_name" {
  type        = string
  description = "Object path for uploaded function source zip"
  default     = "functions/loto-orchestrator/function-source.zip"
}

variable "functions_runtime_service_account_email" {
  type        = string
  description = "Runtime service account email from bootstrap"
}

variable "scheduler_invoker_service_account_email" {
  type        = string
  description = "Scheduler invoker service account email from bootstrap"
}

variable "line_channel_access_token_secret_id" {
  type        = string
  description = "Secret Manager secret id for LINE channel access token"
  default     = "LINE_CHANNEL_ACCESS_TOKEN"
}

variable "line_user_id_secret_id" {
  type        = string
  description = "Secret Manager secret id for LINE user id"
  default     = "LINE_USER_ID"
}

variable "app_env" {
  type        = string
  description = "Application environment"
  default     = "prod"
}

variable "app_timezone" {
  type        = string
  description = "Application timezone"
  default     = "Asia/Tokyo"
}

variable "log_level" {
  type        = string
  description = "Application log level"
  default     = "INFO"
}

variable "log_json" {
  type        = string
  description = "Whether to emit JSON logs"
  default     = "true"
}

variable "service_name" {
  type        = string
  description = "Service name"
  default     = "loto-predict-line"
}

variable "stats_target_draws" {
  type        = number
  description = "Default number of historical draws used for statistics"
  default     = 100
}

variable "prediction_count" {
  type        = number
  description = "Default number of tickets to generate"
  default     = 5
}

variable "loto6_number_min" {
  type    = number
  default = 1
}

variable "loto6_number_max" {
  type    = number
  default = 43
}

variable "loto6_pick_count" {
  type    = number
  default = 6
}

variable "loto7_number_min" {
  type    = number
  default = 1
}

variable "loto7_number_max" {
  type    = number
  default = 37
}

variable "loto7_pick_count" {
  type    = number
  default = 7
}

variable "function_timeout_seconds" {
  type        = number
  description = "Cloud Function timeout"
  default     = 60
}

variable "function_available_memory" {
  type        = string
  description = "Cloud Function memory"
  default     = "512M"
}

variable "function_min_instance_count" {
  type        = number
  description = "Cloud Function min instances"
  default     = 0
}

variable "function_max_instance_count" {
  type        = number
  description = "Cloud Function max instances"
  default     = 1
}

variable "scheduler_loto6_cron" {
  type        = string
  description = "Cron for LOTO6"
  default     = "5 19 * * 1,4"
}

variable "scheduler_loto7_cron" {
  type        = string
  description = "Cron for LOTO7"
  default     = "5 19 * * 5"
}

variable "scheduler_time_zone" {
  type        = string
  description = "Scheduler timezone"
  default     = "Asia/Tokyo"
}
