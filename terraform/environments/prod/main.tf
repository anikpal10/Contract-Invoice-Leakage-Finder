terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

module "storage" {
  source      = "../../modules/storage"
  project_id  = var.project_id
  region      = var.region
  environment = "prod"
}

module "secrets" {
  source      = "../../modules/secret_manager"
  project_id  = var.project_id
  environment = "prod"
}

module "bigquery" {
  source      = "../../modules/bigquery"
  project_id  = var.project_id
  region      = var.region
  environment = "prod"
}

module "cloud_tasks" {
  source      = "../../modules/cloud_tasks"
  project_id  = var.project_id
  region      = var.region
  environment = "prod"
}

module "cloud_run" {
  source          = "../../modules/cloud_run"
  project_id      = var.project_id
  region          = var.region
  environment     = "prod"
  backend_image   = var.backend_image
  frontend_image  = var.frontend_image
  evidence_bucket = module.storage.evidence_bucket_name
  export_bucket   = module.storage.export_bucket_name
}

module "monitoring" {
  source      = "../../modules/monitoring"
  project_id  = var.project_id
  environment = "prod"
}

