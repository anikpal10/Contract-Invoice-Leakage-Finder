# CONTRACT & INVOICE LEAKAGE FINDER

> **Evidence-Grounded B2B Financial Exception Engine & Multi-Way Reconciliation Platform**

A production-oriented B2B SaaS application designed for finance managers, accounts payable analysts, and procurement directors to systematically identify financial leakage across supplier contracts, price schedules, purchase orders, invoices, and goods received notes (GRNs).

---

## Key Capabilities

- **Evidence-Grounded Findings**: Every identified variance links directly to source document citations (page, line, item code).
- **LLM-Powered Intelligent Document Processing & Semantic Matching**:
  - Unified multi-provider LLM service supporting **Google Gemini API** (`google-genai`) and **OpenAI GPT API** (`openai`).
  - **Structured Pydantic Extraction**: Strictly extracts product/service names, descriptions, quantities, unit prices, line totals, tax, discounts, currencies, validity dates, payment terms, and page-level evidence into validated Pydantic models.
  - **Multimodal Vision OCR & Tesseract**: Natively processes scanned PDFs, rasterized documents, and complex visual layouts using Gemini multimodal vision and local `pytesseract`.
  - **Semantic Product Synonym Matching**: Employs LLM understanding to correlate differently worded product descriptions (e.g., brand abbreviations, storage variants) with confidence scoring, while enforcing human review when confidence is below 0.85.
  - **Auditor-Grade Explanations**: Generates neutral, executive explanations for Accounts Payable audit review.
- **100% Deterministic Financial Arithmetic**:
  - Python `Decimal` serves as the **final mathematical authority** — LLMs are never permitted to perform monetary calculations.
  - Formula: `Cost Difference = Invoiced Amount - Expected Contract Amount`. Any difference > 0.00 is flagged as potential cost leakage.
- **Pandas Data Processing & Analytics Engine**:
  - Structured comparison DataFrames for multi-document reconciliation.
  - Instant aggregation of total invoices analyzed, leakage totals, category breakdowns, severity distributions, and top-leakage supplier rankings via `pandas`.
- **Multi-Way Variance Detection**:
  1. Contract Rate vs. Invoice Price Mismatches
  2. Purchase Order vs. Invoice Price Mismatches
  3. Invoiced Quantity Exceeding Purchase Order Authorized Quantity
  4. Invoiced Quantity Exceeding Warehouse Received Receipts (GRN shortfall)
  5. Duplicate Invoices (exact & fuzzy lookback across configurable window)
  6. Invoice Line-Item & Header Arithmetic Verification
  7. Inverted or Missing Credit Note Allowances
- **Human Review Workbench**: Strict human-in-the-loop review workflow. Only authorized reviewers can confirm findings (`CONFIRMED`, `REJECTED`, `NEEDS_MORE_INFO`).
- **Versioned Admin Configuration**: Configure price variance tolerances (percentage & absolute), quantity tolerances, duplicate windows, and review severity thresholds with complete change attribution and version history.
- **Formal Audit Reporting**: Instant generation of structured CSV exports and landscape PDF audit packages using ReportLab.
- **Multi-Tenant Security & RBAC**: Tenant isolation across organizations, workspaces, and cases, with protection against IDOR vulnerabilities.

---

## Technology Stack

- **Frontend**: React 18, TypeScript, Tailwind CSS, Lucide Icons, Vite, React Router 6.
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2.
- **Database**: PostgreSQL (Production) / SQLite (Zero-dependency Local Development & Testing).
- **AI & Processing**: Google Gemini API (`google-genai`), PyPDF, OpenPyXL, RapidFuzz.
- **Reporting**: ReportLab (Vector PDF Generation), Python CSV.
- **Cloud Infrastructure**: Google Cloud Run, Cloud Storage, BigQuery, Cloud Tasks, Secret Manager, Cloud Monitoring, Terraform.
- **DevOps**: Docker multi-stage builds, Docker Compose, GitHub Actions CI/CD.

---

## Quickstart Guide (Local Development)

### 1. Prerequisites
Ensure you have Python 3.12+ and Node.js 20+ installed.

### 2. Start the Backend API
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run database migrations (or SQLite tables auto-initialize)
cd backend
..\.venv\Scripts\alembic.exe upgrade head
cd ..

# Seed the database with the pre-configured demo organization
.\.venv\Scripts\python.exe backend\seed_data.py

# Launch FastAPI backend server
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000`
- Swagger Documentation: `http://localhost:8000/docs`

### 3. Start the Frontend Dashboard
In a separate terminal:
```powershell
cd frontend
npm run dev
```
- Frontend URL: `http://localhost:5173`

---

## Demonstration Credentials (Pre-Seeded)

The system is pre-loaded with **Apex Global Retail Ltd** and 4 role accounts:

| Role | Email | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@apexretail.co.uk` | `Password123!` | Full tenant configuration, versioned rules, user management |
| **Manager** | `manager@apexretail.co.uk` | `Password123!` | Create audit batches, run reconciliations, generate exports |
| **Reviewer** | `reviewer@apexretail.co.uk` | `Password123!` | Inspect evidence citations, confirm/reject exceptions |
| **Viewer** | `viewer@apexretail.co.uk` | `Password123!` | Read-only audit access to cases and reports |

*Tip: The Login screen includes 1-click demo login buttons for instant access!*

---

## LLM Configuration (Optional & Modular)

The application functions completely offline with zero external dependencies using its deterministic heuristic extraction engine. To activate the LLM-powered semantic extraction, multimodal vision OCR, and AI audit analysis, configure environment variables in `.env`:

```env
# Choose provider: "gemini" or "openai"
LLM_PROVIDER=gemini

# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# OpenAI API (Alternative)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
```

---

## Running Automated Tests

Run the full backend test suite covering authentication, tenant isolation, financial reconciliation rules, duplicate detection, human review, export generation, and LLM integration:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/app/tests/ -v
```
*(All 30 unit and integration tests passing: 23 existing tests + 7 LLM integration tests)*

---

## Docker Deployment

To spin up the entire production-like environment with PostgreSQL:

```bash
# Launch multi-container stack
docker-compose up --build -d

# Check status
docker-compose ps
```

---

## Documentation Links

- [Architecture & Data Flow Blueprint](file:///c:/Users/anikp/python%20learning/Contract%20&%20Invoice%20Leakage%20Finder(3)/ARCHITECTURE.md)
- [REST API Documentation](file:///c:/Users/anikp/python%20learning/Contract%20&%20Invoice%20Leakage%20Finder(3)/API_DOCUMENTATION.md)
- [Testing & Quality Assurance Guide](file:///c:/Users/anikp/python%20learning/Contract%20&%20Invoice%20Leakage%20Finder(3)/TESTING_GUIDE.md)
- [Cloud Infrastructure & Deployment Guide](file:///c:/Users/anikp/python%20learning/Contract%20&%20Invoice%20Leakage%20Finder(3)/DEPLOYMENT_GUIDE.md)
- [Demonstration & Walkthrough Guide](file:///c:/Users/anikp/python%20learning/Contract%20&%20Invoice%20Leakage%20Finder(3)/DEMONSTRATION_GUIDE.md)

