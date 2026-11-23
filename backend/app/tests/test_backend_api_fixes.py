import io
import pytest
from backend.app.models.case import ReconciliationCase
from backend.app.models.finding import Finding
from backend.app.models.finding import FindingCategory
from decimal import Decimal

def test_oauth2_token_form_login(client, test_tenants):
    # Tests login with form data compatible with Swagger UI Authorize
    res = client.post(
        "/v1/auth/token",
        data={"username": "admin@acme.com", "password": "Secret123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["email"] == "admin@acme.com"

def test_login_json_with_username_or_email(client, test_tenants):
    # Tests login with 'username' in JSON instead of 'email'
    res = client.post(
        "/v1/auth/login",
        json={"username": "admin@acme.com", "password": "Secret123!"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data

def test_query_param_token_auth(client, test_tenants):
    # Tests authenticating via ?token=... query parameter (used for browser downloads)
    token = test_tenants["token1"]
    res = client.get(f"/v1/cases/?token={token}")
    assert res.status_code == 200, res.text

def test_upload_document_with_auto_category(client, test_tenants, db_session):
    token = test_tenants["token1"]
    user1 = test_tenants["user1"]
    org1 = test_tenants["org1"]
    ws1 = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org1.id,
        workspace_id=ws1.id,
        case_reference="CASE-AUTO-001",
        title="Auto Category Test Case",
        created_by_id=user1.id
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # Upload with category="AUTO"
    dummy_csv = b"Invoice Number,Supplier,Date,Total\nINV-9999,Apex Supplies,2026-01-01,500.00\n"
    res = client.post(
        f"/v1/cases/{case.id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("INV-9999_Invoice.csv", io.BytesIO(dummy_csv), "text/csv")},
        data={"category": "AUTO"}
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["category"] == "INVOICE"

def test_global_findings_list_endpoint(client, test_tenants, db_session):
    token = test_tenants["token1"]
    user1 = test_tenants["user1"]
    org1 = test_tenants["org1"]
    ws1 = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org1.id,
        workspace_id=ws1.id,
        case_reference="CASE-FINDINGS-001",
        title="Findings List Test Case",
        created_by_id=user1.id
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    finding = Finding(
        organization_id=org1.id,
        case_id=case.id,
        finding_category="PRICE_DISCREPANCY",
        supplier_name="Global Supplier",
        invoice_reference="INV-TEST-001",
        potential_difference=150.00,
        expected_amount=100.00,
        invoiced_amount=250.00,
        severity="MEDIUM",
        review_status="NEW",
        calculation_explanation="Test discrepancy"
    )
    db_session.add(finding)
    db_session.commit()

    # Query GET /v1/findings/
    res = client.get("/v1/findings/", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) >= 1
    assert data[0]["invoice_reference"] == "INV-TEST-001"

def test_recent_documents_and_auto_reconcile(client, test_tenants, db_session):
    token = test_tenants["token1"]
    user1 = test_tenants["user1"]
    org1 = test_tenants["org1"]
    ws1 = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org1.id,
        workspace_id=ws1.id,
        case_reference="CASE-REC-DOC-001",
        title="Recent Docs Test Case",
        created_by_id=user1.id
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    dummy_csv = b"Invoice Number,Supplier,Date,Total\nINV-DOC-123,Apex Supplies,2026-01-01,750.00\n"
    res = client.post(
        f"/v1/cases/{case.id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("INV-DOC-123_Invoice.csv", io.BytesIO(dummy_csv), "text/csv")},
        data={"category": "INVOICE"}
    )
    assert res.status_code == 201
    upload_data = res.json()
    assert upload_data["reconciled"] is True

    # Test GET /v1/cases/documents/recent
    res_recent = client.get("/v1/cases/documents/recent", headers={"Authorization": f"Bearer {token}"})
    assert res_recent.status_code == 200
    recent_docs = res_recent.json()
    assert len(recent_docs) >= 1
    assert any(d["original_filename"] == "INV-DOC-123_Invoice.csv" for d in recent_docs)


def test_dashboard_summary_uses_currency_breakdown_without_cross_currency_addition(client, test_tenants, db_session):
    token = test_tenants["token1"]
    user1 = test_tenants["user1"]
    org1 = test_tenants["org1"]
    ws1 = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org1.id,
        workspace_id=ws1.id,
        case_reference="CASE-CURR-001",
        title="Currency Summary Test",
        created_by_id=user1.id,
        currency="REVIEW_REQUIRED",
    )
    db_session.add(case)
    db_session.flush()

    # Eligible overcharge in GBP
    f1 = Finding(
        organization_id=org1.id,
        case_id=case.id,
        finding_category=FindingCategory.CONTRACT_PRICE_MISMATCH.value,
        supplier_name="Supplier A",
        invoice_reference="INV-GBP-1",
        expected_amount=Decimal("100.00"),
        invoiced_amount=Decimal("120.00"),
        potential_difference=Decimal("20.00"),
        currency="GBP",
        severity="LOW",
        review_status="NEW",
        calculation_explanation="GBP overcharge"
    )

    # Eligible overcharge in USD
    f2 = Finding(
        organization_id=org1.id,
        case_id=case.id,
        finding_category=FindingCategory.PO_PRICE_MISMATCH.value,
        supplier_name="Supplier B",
        invoice_reference="INV-USD-1",
        expected_amount=Decimal("200.00"),
        invoiced_amount=Decimal("250.00"),
        potential_difference=Decimal("50.00"),
        currency="USD",
        severity="LOW",
        review_status="NEW",
        calculation_explanation="USD overcharge"
    )

    # Not eligible for gross overcharge KPI
    f3 = Finding(
        organization_id=org1.id,
        case_id=case.id,
        finding_category=FindingCategory.INCORRECT_LINE_TOTAL.value,
        supplier_name="Supplier B",
        invoice_reference="INV-USD-1",
        expected_amount=Decimal("10.00"),
        invoiced_amount=Decimal("12.00"),
        potential_difference=Decimal("2.00"),
        currency="USD",
        severity="LOW",
        review_status="NEW",
        calculation_explanation="Arithmetic mismatch"
    )

    db_session.add_all([f1, f2, f3])
    db_session.commit()

    res = client.get("/v1/cases/summary/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    data = res.json()

    # Cross-currency totals must remain in breakdown only
    assert float(data["potential_leakage"]) == 0.0
    assert float(data["potential_leakage_by_currency"]["GBP"]) == 20.0
    assert float(data["potential_leakage_by_currency"]["USD"]) == 50.0
    assert data["currency_status"] == "MIXED"

