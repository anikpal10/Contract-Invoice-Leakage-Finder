variable "project_id" { type = string }
variable "environment" { type = string }

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "cil-jwt-secret-${var.environment}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "cil-gemini-api-key-${var.environment}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "cil-database-url-${var.environment}"
  replication {
    auto {}
  }
}

output "jwt_secret_id" {
  value = google_secret_manager_secret.jwt_secret.id
}

output "gemini_secret_id" {
  value = google_secret_manager_secret.gemini_api_key.id
}

output "database_url_id" {
  value = google_secret_manager_secret.database_url.id
}

