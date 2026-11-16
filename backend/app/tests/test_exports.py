from decimal import Decimal
from fastapi import status
from backend.app.models.case import ReconciliationCase
from backend.app.models.finding import Finding, FindingCategory, Severity, ReviewStatus

def test_generate_csv_and_pdf_exports(client, test_tenants, db_session):
    org = test_tenants["org1"]
    ws = test_tenants["ws1"]
    token = test_tenants["token1"]
    headers = {"Authorization": f"Bearer {token}"}

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Export Test Case",
        case_reference="CASE-EXP-001"
    )
    db_session.add(case)
    db_session.flush()

    f1 = Finding(
        case_id=case.id,
        organization_id=org.id,
        finding_category=FindingCategory.CONTRACT_PRICE_MISMATCH.value,
        supplier_name="Export Supplier A",
        invoice_reference="INV-EXP-1",
        expected_amount=Decimal("5000.00"),
        invoiced_amount=Decimal("5500.00"),
        potential_difference=Decimal("500.00"),
        severity=Severity.HIGH.value,
        review_status=ReviewStatus.CONFIRMED.value,
        calculation_explanation="Contract rate variance",
        rule_version=1
    )
    db_session.add(f1)
    db_session.commit()

    # 1. Generate CSV Export
    r_csv = client.post(
        f"/v1/cases/{case.id}/exports",
        json={"format": "CSV", "include_rejected": False},
        headers=headers
    )
    assert r_csv.status_code == status.HTTP_201_CREATED
    csv_data = r_csv.json()
    assert csv_data["format"] == "CSV"
    assert csv_data["record_count"] == 1
    assert Decimal(str(csv_data["total_leakage_amount"])) == Decimal("500.00")

    # 2. Download CSV File
    download_url = csv_data["download_url"]
    r_download = client.get(download_url, headers=headers)
    assert r_download.status_code == status.HTTP_200_OK
    assert "Export Supplier A" in r_download.text

    # 3. Generate PDF Export
    r_pdf = client.post(
        f"/v1/cases/{case.id}/exports",
        json={"format": "PDF", "include_rejected": False},
        headers=headers
    )
    assert r_pdf.status_code == status.HTTP_201_CREATED
    pdf_data = r_pdf.json()
    assert pdf_data["format"] == "PDF"

    # 4. Download PDF File
    r_pdf_download = client.get(pdf_data["download_url"], headers=headers)
    assert r_pdf_download.status_code == status.HTTP_200_OK
    assert r_pdf_download.headers["content-type"] == "application/pdf"
    assert len(r_pdf_download.content) > 500  # PDF binary content generated

