variable "project_id" { type = string }
variable "region" { type = string; default = "europe-west2" }
variable "environment" { type = string }
variable "backend_image" { type = string }
variable "frontend_image" { type = string }
variable "evidence_bucket" { type = string }
variable "export_bucket" { type = string }

# Least privilege service account for backend
resource "google_service_account" "backend_sa" {
  account_id   = "cil-backend-${var.environment}"
  display_name = "Contract & Invoice Leakage Backend SA (${var.environment})"
}

# Grant GCS access
resource "google_storage_bucket_iam_member" "backend_gcs_evidence" {
  bucket = var.evidence_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_storage_bucket_iam_member" "backend_gcs_export" {
  bucket = var.export_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.backend_sa.email}"
}

# Backend Cloud Run Service
resource "google_cloud_run_v2_service" "backend" {
  name     = "cil-api-${var.environment}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.backend_sa.email
    scaling {
      min_instance_count = var.environment == "prod" ? 2 : 0
      max_instance_count = 10
    }

    containers {
      image = var.backend_image
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "STORAGE_BACKEND"
        value = "gcs"
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = var.evidence_bucket
      }
      env {
        name  = "GCS_EXPORT_BUCKET"
        value = var.export_bucket
      }
    }
  }
}

# Frontend Cloud Run Service
resource "google_cloud_run_v2_service" "frontend" {
  name     = "cil-ui-${var.environment}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = var.environment == "prod" ? 1 : 0
      max_instance_count = 5
    }

    containers {
      image = var.frontend_image
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }
}

# Allow public unauthenticated invocation (secured by JWT application layer)
resource "google_cloud_run_service_iam_member" "public_backend" {
  location = google_cloud_run_v2_service.backend.location
  service  = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "public_frontend" {
  location = google_cloud_run_v2_service.frontend.location
  service  = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}

output "frontend_url" {
  value = google_cloud_run_v2_service.frontend.uri
}

