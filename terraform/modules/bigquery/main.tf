variable "project_id" { type = string }
variable "region" { type = string; default = "europe-west2" }
variable "environment" { type = string }

resource "google_bigquery_dataset" "leakage_dataset" {
  dataset_id                  = "cil_analytics_${var.environment}"
  friendly_name               = "Contract & Invoice Leakage Analytics"
  description                 = "Structured analytical datastore for leakage exceptions and audit trails"
  location                    = var.region
  default_table_expiration_ms = null

  labels = {
    env = var.environment
    app = "contract-invoice-leakage-finder"
  }
}

resource "google_bigquery_table" "findings_table" {
  dataset_id = google_bigquery_dataset.leakage_dataset.dataset_id
  table_id   = "reconciliation_findings"

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["organization_id", "supplier_name", "finding_category"]

  schema = <<EOF
[
  {"name": "finding_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "organization_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "case_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "supplier_name", "type": "STRING", "mode": "REQUIRED"},
  {"name": "invoice_reference", "type": "STRING", "mode": "REQUIRED"},
  {"name": "finding_category", "type": "STRING", "mode": "REQUIRED"},
  {"name": "expected_amount", "type": "NUMERIC", "mode": "REQUIRED"},
  {"name": "invoiced_amount", "type": "NUMERIC", "mode": "REQUIRED"},
  {"name": "potential_difference", "type": "NUMERIC", "mode": "REQUIRED"},
  {"name": "currency", "type": "STRING", "mode": "REQUIRED"},
  {"name": "severity", "type": "STRING", "mode": "REQUIRED"},
  {"name": "review_status", "type": "STRING", "mode": "REQUIRED"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"}
]
EOF
}

output "dataset_id" {
  value = google_bigquery_dataset.leakage_dataset.dataset_id
}

