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

def test_export_scoped_to_document(client, test_tenants, db_session):
    from backend.app.models.document import UploadedDocument

    org = test_tenants["org1"]
    ws = test_tenants["ws1"]
    token = test_tenants["token1"]
    headers = {"Authorization": f"Bearer {token}"}

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Document Scoped Export Case",
        case_reference="CASE-EXP-002"
    )
    db_session.add(case)
    db_session.flush()

    # Create Document A (Current Upload)
    doc_a = UploadedDocument(
        case_id=case.id,
        organization_id=org.id,
        filename="INV-DOC-A.pdf",
        original_filename="INV-DOC-A.pdf",
        file_type="PDF",
        category="INVOICE",
        storage_path="tmp/inv_doc_a.pdf",
        file_size_bytes=1024,
        sha256_hash="hash_doc_a_123456",
        processing_status="EXTRACTED",
        extracted_metadata={"invoice_number": "INV-A"}
    )
    # Create Document B (Previous Upload)
    doc_b = UploadedDocument(
        case_id=case.id,
        organization_id=org.id,
        filename="INV-DOC-B.pdf",
        original_filename="INV-DOC-B.pdf",
        file_type="PDF",
        category="INVOICE",
        storage_path="tmp/inv_doc_b.pdf",
        file_size_bytes=2048,
        sha256_hash="hash_doc_b_654321",
        processing_status="EXTRACTED",
        extracted_metadata={"invoice_number": "INV-B"}
    )
    db_session.add_all([doc_a, doc_b])
    db_session.flush()

    # Finding A for Document A (Current Upload)
    f_a = Finding(
        case_id=case.id,
        organization_id=org.id,
        finding_category=FindingCategory.CONTRACT_PRICE_MISMATCH.value,
        supplier_name="Supplier A",
        invoice_reference="INV-A",
        expected_amount=Decimal("1000.00"),
        invoiced_amount=Decimal("1500.00"),
        potential_difference=Decimal("500.00"),
        severity=Severity.HIGH.value,
        review_status=ReviewStatus.CONFIRMED.value,
        calculation_explanation="Overcharge on Doc A",
        source_document_references=[{"document_id": doc_a.id, "invoice_number": "INV-A"}],
        rule_version=1
    )
    # Finding B for Document B (Previous Upload)
    f_b = Finding(
        case_id=case.id,
        organization_id=org.id,
        finding_category=FindingCategory.CONTRACT_PRICE_MISMATCH.value,
        supplier_name="Supplier B",
        invoice_reference="INV-B",
        expected_amount=Decimal("2000.00"),
        invoiced_amount=Decimal("3000.00"),
        potential_difference=Decimal("1000.00"),
        severity=Severity.HIGH.value,
        review_status=ReviewStatus.CONFIRMED.value,
        calculation_explanation="Overcharge on Doc B",
        source_document_references=[{"document_id": doc_b.id, "invoice_number": "INV-B"}],
        rule_version=1
    )
    db_session.add_all([f_a, f_b])
    db_session.commit()

    # 1. Export PDF scoped ONLY to Document A
    res_a = client.post(
        f"/v1/cases/{case.id}/exports",
        json={"format": "PDF", "document_id": doc_a.id, "include_rejected": False},
        headers=headers
    )
    assert res_a.status_code == status.HTTP_201_CREATED
    data_a = res_a.json()
    assert data_a["record_count"] == 1  # ONLY Doc A's finding!
    assert Decimal(str(data_a["total_leakage_amount"])) == Decimal("500.00")
    assert "INV-DOC-A" in data_a["file_name"]

    # 2. Check full dossier scoped to Document A
    dossier_res = client.get(
        f"/v1/cases/{case.id}/full-dossier?document_id={doc_a.id}",
        headers=headers
    )
    assert dossier_res.status_code == status.HTTP_200_OK
    dossier_data = dossier_res.json()
    assert dossier_data["stats"]["total_findings"] == 1
    assert dossier_data["findings"][0]["invoice_reference"] == "INV-A"

    # 3. Export PDF with all documents (no filter)
    res_all = client.post(
        f"/v1/cases/{case.id}/exports",
        json={"format": "PDF", "include_rejected": False},
        headers=headers
    )
    assert res_all.status_code == status.HTTP_201_CREATED
    data_all = res_all.json()
    assert data_all["record_count"] == 2  # Both findings included
    assert Decimal(str(data_all["total_leakage_amount"])) == Decimal("1500.00")

