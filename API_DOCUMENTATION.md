# REST API Documentation

## Contract & Invoice Leakage Finder v1.0

### Base URL
- Local: `http://localhost:8000/v1`
- Cloud Run: `https://cil-api-[env]-[hash].a.run.app/v1`

---

### Authentication & Authorization

All authenticated endpoints require an `Authorization` header with a Bearer JWT:
```http
Authorization: Bearer <access_token>
```

#### Roles:
- `ADMIN`: Full tenant management, configuration updating, user management.
- `MANAGER`: Case management, running reconciliations, reports generation.
- `REVIEWER`: Inspecting evidence, approving/rejecting findings, commenting.
- `VIEWER`: Read-only access to cases, findings, and audit history.

---

### Endpoints

#### 1. Authentication
- `POST /v1/auth/register`
  - Registers a new organization tenant, default workspace, admin user, and baseline rule configuration.
  - Request: `{ "email": "...", "password": "...", "full_name": "...", "organization_name": "..." }`
  - Response: `201 Created` with access token & refresh token.
- `POST /v1/auth/login`
  - Authenticates user credentials.
  - Request: `{ "email": "...", "password": "..." }`
  - Response: `200 OK` with access token & refresh token.
- `POST /v1/auth/refresh`
  - Issues new access token from valid refresh token.
- `GET /v1/auth/me`
  - Returns authenticated user details and organization ID.

#### 2. Workspaces & Suppliers
- `GET /v1/workspaces/` - List organization workspaces.
- `POST /v1/workspaces/` - Create a new workspace.
- `GET /v1/suppliers/` - List registered suppliers.
- `POST /v1/suppliers/` - Create new supplier entity with canonical naming.

#### 3. Reconciliation Cases
- `GET /v1/cases/` - List cases in tenant.
- `POST /v1/cases/` - Create a new reconciliation case.
- `GET /v1/cases/{case_id}` - Get case detail with summary counts and leakage exposure.
- `POST /v1/cases/{case_id}/run` - Execute deterministic financial reconciliation engine across all ingested documents. Returns list of detected exceptions.
- `GET /v1/cases/summary/dashboard` - Get high-level KPI dashboard metrics.

#### 4. Document Ingestion & Provenance
- `POST /v1/cases/{case_id}/documents`
  - Upload evidence file (PDF, CSV, XLSX) with multipart form data (`file`, `category`).
  - Automatically calculates SHA-256 hash to prevent duplicate uploads.
  - Automatically triggers AI or local heuristic extraction.
- `GET /v1/cases/{case_id}/documents` - List all uploaded documents and processing status.
- `GET /v1/cases/{case_id}/documents/{document_id}/fields` - List field-level extraction provenance, page/row locations, confidence scores.
- `PATCH /v1/cases/fields/{field_id}` - Edit permitted extracted field values with audit logging.

#### 5. Findings Management & Human Review
- `GET /v1/cases/{case_id}/findings` - List findings with calculated variance, severity, and status.
- `GET /v1/findings/{finding_id}` - Detailed finding view with side-by-side math, source citations, and decision trail.
- `PATCH /v1/findings/{finding_id}` - Update review status and optional adjusted amount.
- `POST /v1/findings/{finding_id}/decisions` - Record review decision (`CONFIRM`, `REJECT`, `REQUEST_INFO`).

#### 6. Reports & Exports
- `POST /v1/cases/{case_id}/exports`
  - Request: `{ "format": "CSV" | "PDF", "include_rejected": false }`
  - Generates immutable report with audit log and returns download URL.
- `GET /v1/cases/{case_id}/exports/{export_id}/download` - Download generated CSV or PDF.

#### 7. Admin Configuration
- `GET /v1/admin/rule-config` - Get active versioned tolerance rules.
- `PUT /v1/admin/rule-config` - Deploy new immutable version of rules (Admin only).
- `GET /v1/admin/rule-config/history` - List all historical rule versions.

#### 8. Audit History & User Management
- `GET /v1/audit/` - Chronological audit events.
- `GET /v1/users/` - List tenant users.
- `POST /v1/users/` - Create tenant user.
- `PATCH /v1/users/{user_id}` - Modify user status or role.

