variable "project_id" { type = string }
variable "region" { type = string; default = "europe-west2" }
variable "environment" { type = string }

resource "google_storage_bucket" "evidence_bucket" {
  name          = "${var.project_id}-cil-evidence-${var.environment}"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "SetStorageClass"
      storage_class = "NEARLINE"
    }
    condition {
      age = 90
    }
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 365 * 7 # 7-year audit retention
    }
  }
}

resource "google_storage_bucket" "export_bucket" {
  name          = "${var.project_id}-cil-exports-${var.environment}"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 30 # Temporary export download retention
    }
  }
}

output "evidence_bucket_name" {
  value = google_storage_bucket.evidence_bucket.name
}

output "export_bucket_name" {
  value = google_storage_bucket.export_bucket.name
}

