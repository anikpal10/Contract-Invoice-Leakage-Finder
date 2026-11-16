# Testing & Quality Assurance Guide

## Overview

The **Contract & Invoice Leakage Finder** test suite is built on `pytest` and `TestClient` (FastAPI), providing automated end-to-end verification of tenant isolation, multi-way deterministic financial reconciliation, human review decisions, and report generation.

---

## Running the Automated Test Suite

From the workspace root directory:

```bash
# Run all backend unit & integration tests
.\.venv\Scripts\python.exe -m pytest backend/app/tests/ -v

# Run with coverage report
.\.venv\Scripts\python.exe -m pytest backend/app/tests/ -v --cov=backend/app --cov-report=term-missing
```

---

## Test Modules & Coverage

| Test File | Scope | Verifications |
| :--- | :--- | :--- |
| `test_auth.py` | Authentication & Security | User registration, duplicate email rejection, login, bcrypt verification, JWT access & refresh token lifecycle. |
| `test_tenant_isolation.py` | Tenancy & IDOR Defense | Verifies that Tenant A cannot list, view, edit, or delete users, workspaces, or findings belonging to Tenant B (returns 404 Not Found to prevent data probing). |
| `test_reconciliation_engine.py` | Deterministic Financial Engine | Decimal arithmetic accuracy: contract rate variance, PO price variance, quantity billed exceeding ordered, quantity billed exceeding GRN received, duplicate invoices, and math checks. |
| `test_human_review.py` | Human Review Workflow | Approving findings (`CONFIRMED`), rejecting (`REJECTED`), requesting more information (`NEEDS_MORE_INFO`), and immutable audit trail generation. |
| `test_exports.py` | Reporting & Exports | Validates dynamic CSV and PDF generation using ReportLab, download URLs, and leakage exposure totals. |
| `test_admin_config.py` | Versioned Rules & RBAC | Admin rule creation, version incrementation, active state switching, and RBAC rejection of unauthorized user modifications. |

---

## Synthetic Testing Dataset

The platform includes a dedicated dataset generator in `synthetic_dataset/generate_dataset.py`.

```bash
.\.venv\Scripts\python.exe synthetic_dataset\generate_dataset.py
```

### Dataset Structure:
- **65 Invoices**:
  - Correct invoices matching contract & PO perfectly
  - Contract price overcharges (£55 billed vs £50 contracted)
  - Quantity overbilled beyond PO order quantity
  - Duplicate invoices with identical invoice numbers & supplier names
  - Quantity overbilled beyond goods received warehouse notes (GRN shortfall)
  - Inverted / uncredited return fees
- **25 Purchase Orders**: Varied line item descriptions, order quantities, and unit rates.
- **20 Contracts & Price Schedules**: Agreed master pricing across 16 commercial supplier layouts.
- **15 Goods Received Notes (GRNs)**: Warehouse delivery receipts with delivery quantities.

