"""Integration tests for the browser batch-upload flow.

These tests exercise the exact endpoint the frontend file picker calls:
    POST /v1/cases/{case_id}/documents/batch-upload

They assert that the response is shaped so the frontend can immediately render
the AutomatedRecognitionPipelineView (i.e. the "next process" after upload).
"""

import io

from backend.app.models.case import ReconciliationCase
from backend.app.models.document import UploadedDocument


SAMPLE_INVOICE_CSV = (
    "product_name,quantity,invoice_price,invoice_number,invoice_date,supplier_name\n"
    "Cloud Compute Instance,10,120.00,INV-2026-1001,2026-01-15,Apex Cloud Ltd\n"
    "Object Storage GB,500,0.02,INV-2026-1001,2026-01-15,Apex Cloud Ltd\n"
    "Managed Database,2,450.00,INV-2026-1001,2026-01-15,Apex Cloud Ltd\n"
)


def _make_case(db_session, test_tenants, reference="CASE-BATCH-001"):
    case = ReconciliationCase(
        organization_id=test_tenants["org1"].id,
        workspace_id=test_tenants["ws1"].id,
        case_reference=reference,
        title="Batch Upload Flow Test Case",
        created_by_id=test_tenants["user1"].id,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


def test_batch_upload_returns_pipeline_payload(client, test_tenants, db_session):
    """A successful browser upload must return a pipeline-shaped payload."""
    token = test_tenants["token1"]
    case = _make_case(db_session, test_tenants)

    res = client.post(
        f"/v1/cases/{case.id}/documents/batch-upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[
            ("files", ("sample_invoice.csv", io.BytesIO(SAMPLE_INVOICE_CSV.encode()), "text/csv")),
        ],
        data={"category": "AUTO"},
    )

    assert res.status_code == 201, res.text
    data = res.json()

    # Core counters
    assert data["uploaded_count"] == 1
    assert data["skipped_count"] == 0
    assert data["error_count"] == 0
    assert data["case_id"] == case.id
    assert data["document_id"] is not None

    # The document was actually persisted and extracted
    doc = db_session.query(UploadedDocument).filter(UploadedDocument.id == data["document_id"]).first()
    assert doc is not None
    assert doc.original_filename == "sample_invoice.csv"
    assert doc.category == "INVOICE"

    # Pipeline payload required by AutomatedRecognitionPipelineView
    pipeline = data.get("pipeline")
    assert pipeline is not None, "batch-upload must return a pipeline payload"
    assert pipeline["case_id"] == case.id
    assert pipeline["original_filename"] == "sample_invoice.csv"
    assert pipeline["category"] == "INVOICE"
    assert "recognized_data" in pipeline
    assert isinstance(pipeline["automated_steps"], list) and pipeline["automated_steps"]
    assert isinstance(pipeline["findings"], list)

    # Top-level fields the frontend also reads directly
    assert isinstance(data["automated_steps"], list) and data["automated_steps"]
    assert isinstance(data["findings"], list)


def test_batch_upload_rejects_empty_file_list(client, test_tenants, db_session):
    """Posting with no files must fail loudly instead of reporting fake success."""
    token = test_tenants["token1"]
    case = _make_case(db_session, test_tenants, reference="CASE-BATCH-002")

    res = client.post(
        f"/v1/cases/{case.id}/documents/batch-upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"category": "AUTO"},
    )

    # FastAPI returns 422 for a missing required multipart field; either way it
    # must not be a 2xx "success".
    assert res.status_code in (400, 422), res.text


def test_batch_upload_rejects_unsupported_file_type(client, test_tenants, db_session):
    """An unsupported extension must surface a 400, not a fake success."""
    token = test_tenants["token1"]
    case = _make_case(db_session, test_tenants, reference="CASE-BATCH-003")

    res = client.post(
        f"/v1/cases/{case.id}/documents/batch-upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[
            ("files", ("malware.exe", io.BytesIO(b"MZ\x90\x00binary"), "application/octet-stream")),
        ],
        data={"category": "AUTO"},
    )

    assert res.status_code == 400, res.text
    assert "No files could be ingested" in res.json()["detail"]


def test_batch_upload_duplicate_is_counted_as_skipped(client, test_tenants, db_session):
    """Re-uploading the same file must increment skipped_count, not error_count."""
    token = test_tenants["token1"]
    case = _make_case(db_session, test_tenants, reference="CASE-BATCH-004")

    payload = SAMPLE_INVOICE_CSV.encode()
    first = client.post(
        f"/v1/cases/{case.id}/documents/batch-upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("dup_invoice.csv", io.BytesIO(payload), "text/csv"))],
        data={"category": "AUTO"},
    )
    assert first.status_code == 201, first.text
    assert first.json()["uploaded_count"] == 1

    second = client.post(
        f"/v1/cases/{case.id}/documents/batch-upload",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("dup_invoice.csv", io.BytesIO(payload), "text/csv"))],
        data={"category": "AUTO"},
    )
    assert second.status_code == 201, second.text
    data = second.json()
    assert data["skipped_count"] == 1
    assert data["error_count"] == 0
    assert data["pipeline"] is not None
