output "backend_url" {
  value = module.cloud_run.backend_url
}

output "frontend_url" {
  value = module.cloud_run.frontend_url
}

output "evidence_bucket" {
  value = module.storage.evidence_bucket_name
}

