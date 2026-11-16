variable "project_id" {
  type        = string
  description = "GCP Project ID for development"
}

variable "region" {
  type        = string
  default     = "europe-west2"
}

variable "backend_image" {
  type        = string
  default     = "europe-west2-docker.pkg.dev/my-gcp-project/cil-repo/backend:latest"
}

variable "frontend_image" {
  type        = string
  default     = "europe-west2-docker.pkg.dev/my-gcp-project/cil-repo/frontend:latest"
}

