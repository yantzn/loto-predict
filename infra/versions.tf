terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }

    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }

    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.5"
    }
  }
}
