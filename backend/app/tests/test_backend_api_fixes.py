import io
import pytest
from backend.app.models.case import ReconciliationCase
from backend.app.models.finding import Finding

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


