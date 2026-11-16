terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

variable "project_id" {
  type        = string
  description = "GCP Project ID"
}

variable "region" {
  type        = string
  default     = "europe-west2"
  description = "Default GCP Region (London)"
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
}

resource "google_storage_bucket" "tf_state" {
  name          = "${var.project_id}-tfstate-${var.environment}"
  location      = var.region
  force_destroy = false

  versioning {
    enabled = true
  }

  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      num_newer_versions = 5
      with_state         = "ARCHIVED"
    }
  }
}

output "state_bucket_name" {
  value = google_storage_bucket.tf_state.name
}

