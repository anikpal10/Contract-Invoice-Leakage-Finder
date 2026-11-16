import os
import pytest
from backend.app.models.case import ReconciliationCase

def test_direct_file_path_ingest_zero_memory(client, test_tenants, db_session):
    headers = {"Authorization": f"Bearer {test_tenants['token1']}"}
    user1 = test_tenants["user1"]
    org1 = test_tenants["org1"]
    ws1 = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org1.id,
        workspace_id=ws1.id,
        case_reference="CASE-PATH-001",
        title="Direct Path Test Case",
        created_by_id=user1.id
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # Test single file path using synthetic dataset invoice
    sample_file = "synthetic_dataset/sample_files/invoices/INV-2026-1001.csv"
    assert os.path.exists(sample_file), f"Sample file not found at {sample_file}"

    res = client.post(
        f"/v1/cases/{case.id}/documents/by-path",
        headers=headers,
        json={"file_path": sample_file, "category": "INVOICE"}
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["case_id"] == case.id
    assert "INV-2026-1001.csv" in data["original_filename"]
    assert data["category"] == "INVOICE"
    assert data["processing_status"] in ("EXTRACTED", "PENDING")

    # Duplicate check: ingesting the exact same file path again should detect duplicate SHA-256
    res_dup = client.post(
        f"/v1/cases/{case.id}/documents/by-path",
        headers=headers,
        json={"file_path": sample_file, "category": "INVOICE"}
    )
    assert res_dup.status_code == 201
    dup_data = res_dup.json()
    assert "already registered" in dup_data["message"]

def test_direct_folder_batch_ingest_zero_memory(client, test_tenants, db_session):
    headers = {"Authorization": f"Bearer {test_tenants['token1']}"}
    user1 = test_tenants["user1"]
    org1 = test_tenants["org1"]
    ws1 = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org1.id,
        workspace_id=ws1.id,
        case_reference="CASE-PATH-002",
        title="Direct Folder Path Test Case",
        created_by_id=user1.id
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    sample_folder = "synthetic_dataset/sample_files/contracts"
    assert os.path.exists(sample_folder), f"Sample folder not found at {sample_folder}"

    res = client.post(
        f"/v1/cases/{case.id}/documents/by-folder",
        headers=headers,
        json={"folder_path": sample_folder, "category": "AUTO"}
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["case_id"] == case.id
    assert data["total_found"] > 0
    assert data["ingested_count"] > 0
    assert len(data["results"]) == data["total_found"]
