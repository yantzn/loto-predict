variable "project_id" {
  type        = string
  description = "GCP project id"
}

variable "region" {
  type        = string
  description = "Default GCP region"
  default     = "asia-northeast1"
}

variable "tfstate_location" {
  type        = string
  description = "Location for Terraform state bucket"
  default     = "ASIA"
}

variable "github_repository" {
  type        = string
  description = "GitHub repository in owner/repo format"
}

variable "github_repository_owner" {
  type        = string
  description = "GitHub repository owner"
}

variable "rotation_key" {
  type        = string
  description = "Changing this rotates suffix-based resource names"
  default     = "v1"
}

variable "enable_firestore" {
  type        = bool
  description = "Whether to create Firestore Native database in bootstrap"
  default     = false
}

variable "wif_pool_id" {
  type        = string
  description = "Workload Identity Pool id"
  default     = "github-actions-pool"
}

variable "wif_provider_id" {
  type        = string
  description = "Workload Identity Provider id"
  default     = "github-actions-provider"
}
