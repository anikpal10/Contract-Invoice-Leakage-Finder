variable "project_id" { type = string }
variable "environment" { type = string }
variable "alert_email" { type = string; default = "ops@example.com" }

resource "google_monitoring_notification_channel" "email" {
  display_name = "Finance & DevOps On-Call (${var.environment})"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
}

resource "google_monitoring_alert_policy" "high_severity_exceptions" {
  display_name = "High Leakage Exception Spike (${var.environment})"
  combiner     = "OR"
  conditions {
    display_name = "Cloud Run 5xx Errors"
    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND metric.label.response_code_class=\"5xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
}

output "alert_policy_id" {
  value = google_monitoring_alert_policy.high_severity_exceptions.id
}

