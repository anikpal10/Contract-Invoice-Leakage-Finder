# Cloud Infrastructure & Deployment Guide

## 1. Local Development Setup

### Prerequisites
- Python 3.12+ (Virtual environment in `.venv`)
- Node.js 20+ & npm

### Starting Backend API
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```
Interactive API docs available at: `http://localhost:8000/docs`

### Starting Frontend SPA
```powershell
cd frontend
npm run dev
```
UI available at: `http://localhost:5173`

---

## 2. Docker & Container Deployment

To launch the entire stack locally with PostgreSQL:

```bash
# Build and run containers
docker-compose up --build -d

# View status
docker-compose ps

# Seed demo data inside backend container
docker-compose exec backend python backend/seed_data.py
```

Frontend UI will be accessible on `http://localhost:3000` and API on `http://localhost:8000`.

---

## 3. Google Cloud Platform (Cloud Run & Terraform)

### Architecture Topology
- **API & Worker**: Google Cloud Run (Autoscaling 0-10 instances, least-privilege IAM SA)
- **Frontend**: Google Cloud Run (Nginx Alpine container)
- **Evidence Storage**: Google Cloud Storage (`cil-evidence-[env]`) with 7-year Nearline retention lifecycle.
- **Temporary Exports**: Google Cloud Storage (`cil-exports-[env]`) with 30-day auto-delete lifecycle.
- **Analytics & BigQuery**: BigQuery dataset `cil_analytics_[env]` partitioned by day.
- **Task Queues**: Cloud Tasks `cil-extraction-queue-[env]` with 5-attempt exponential backoff.
- **Secrets**: Google Secret Manager (`cil-jwt-secret`, `cil-gemini-api-key`, `cil-database-url`).

### Deploying with Terraform
```bash
cd terraform/environments/staging

# Initialize Terraform
terraform init

# Validate Plan
terraform plan -var-file="terraform.tfvars"

# Apply Infrastructure
terraform apply -var-file="terraform.tfvars"
```

---

## 4. Rollback & Disaster Recovery Procedures

1. **Cloud Run Revision Rollback**:
   To immediately revert traffic to a previously verified stable revision:
   ```bash
   gcloud run services update-traffic cil-api-prod \
     --to-revisions=cil-api-prod-00012-abc=100 \
     --region=europe-west2
   ```

2. **Database Migration Rollback**:
   ```bash
   cd backend
   alembic downgrade -1
   ```

3. **Storage Version Recovery**:
   GCS evidence buckets have Object Versioning enabled. Deleted or overwritten files can be restored via:
   ```bash
   gcloud storage cp gs://cil-evidence-prod/path/file#VERSION_ID gs://cil-evidence-prod/path/file
   ```

