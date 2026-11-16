# Demonstration & User Acceptance Walkthrough

## Overview

This guide walks through the end-to-end user journey for **Contract & Invoice Leakage Finder**, replicating the exact scenario outlined in Section 17 of the specification.

---

## Demonstration Credentials (Pre-Seeded)

The database is pre-seeded with 4 user roles belonging to tenant organization **Apex Global Retail Ltd**:

| Role | Email | Password | Scope & Responsibilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@apexretail.co.uk` | `Password123!` | Rule configurations, tolerance versions, user management. |
| **Manager** | `manager@apexretail.co.uk` | `Password123!` | Creating audit cases, running reconciliation, generating reports. |
| **Reviewer** | `reviewer@apexretail.co.uk` | `Password123!` | Inspecting evidence citations, approving/rejecting findings. |
| **Viewer** | `viewer@apexretail.co.uk` | `Password123!` | Read-only audit access to reports and history. |

---

## Step-by-Step Demonstration Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Financial Analyst
    participant UI as React Dashboard
    participant API as FastAPI Backend
    participant Engine as Reconciliation Engine
    participant DB as Database / Storage

    User->>UI: 1. Sign In (Manager or Reviewer)
    UI->>API: POST /v1/auth/login
    API-->>UI: Return JWT Token & Org Metadata

    User->>UI: 2. Navigate to "New Reconciliation"
    UI->>API: POST /v1/cases/ (Title, Supplier, Workspace)
    API-->>UI: Return Created Case (CASE-202610-APX01)

    User->>UI: 3. Ingest Documents (Contract, PO, Invoice, GRN)
    UI->>API: POST /v1/cases/{id}/documents
    API->>DB: Compute SHA-256 & Store File
    API->>API: Trigger AI / Heuristic Extraction
    API-->>UI: Extraction Complete & Field Provenance Recorded

    User->>UI: 4. Inspect Processing Status & Field Values
    UI->>API: GET /v1/cases/{id}/documents/{doc_id}/fields
    API-->>UI: Return field provenance, page citations, confidence

    User->>UI: 5. Click "Run Financial Reconciliation"
    UI->>API: POST /v1/cases/{id}/run
    API->>Engine: Run Deterministic Decimal Arithmetic
    Engine-->>API: 16 Evidence-Linked Findings Detected
    API-->>UI: Display Results & Breakdown

    User->>UI: 6. Human Review Workbench
    User->>UI: Inspect Finding & Confirm Exception
    UI->>API: POST /v1/findings/{id}/decisions (action: CONFIRM)
    API->>DB: Record ReviewDecision & Immutable AuditLog
    API-->>UI: Status updated to CONFIRMED

    User->>UI: 7. Export Audit Report
    UI->>API: POST /v1/cases/{id}/exports (format: PDF / CSV)
    API-->>UI: Generated ReportLab PDF download link
```

---

## Walkthrough Scenario: Concrete Leakage Example

### The Scenario:
- **Supplier**: Apex Industrial Supplies Ltd
- **Agreed Contract Unit Price**: £50.00 (Contract `CTR-APX-2026-01`, item `ITM-APX-01`)
- **Authorized Purchase Order Price**: £50.00 (PO `PO-2026-101`, quantity 100 units)
- **Supplier Invoice**: Invoiced unit price £55.00 for quantity 100 units
- **Expected Amount**: £50.00 × 100 = £5,000.00
- **Invoiced Amount**: £55.00 × 100 = £5,500.00
- **Potential Leakage Overcharge**: **£500.00**

### In the Application:
1. Log in as `manager@apexretail.co.uk`.
2. Open the case **"Apex Industrial Supplies Q4 Review"**.
3. Go to **"Reconciliation Results"**.
4. Observe the **Contract Price Mismatch** finding:
   - Expected: `£5,000.00`
   - Invoiced: `£5,500.00`
   - Variance: `+£500.00` (Severity: `HIGH`)
5. Click **"Inspect"** to view side-by-side math and exact citations to `CTR-APX-2026-01` and invoice `INV-2026-1032`.
6. Add reviewer note: `"Confirmed variance with procurement rate card."` and click **"Confirm Exception"**.
7. Navigate to **"Reports & Exports"**, click **"Export Formal PDF Report"**, and download the audit-ready summary package!

