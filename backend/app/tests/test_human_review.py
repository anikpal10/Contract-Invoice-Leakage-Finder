from decimal import Decimal
from fastapi import status
from backend.app.models.case import ReconciliationCase
from backend.app.models.finding import Finding, FindingCategory, Severity, ReviewStatus

def test_human_review_approval_and_rejection(client, test_tenants, db_session):
    org = test_tenants["org1"]
    ws = test_tenants["ws1"]
    token = test_tenants["token1"]
    headers = {"Authorization": f"Bearer {token}"}

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Review Test Case",
        case_reference="CASE-REV-001"
    )
    db_session.add(case)
    db_session.flush()

    finding = Finding(
        case_id=case.id,
        organization_id=org.id,
        finding_category=FindingCategory.CONTRACT_PRICE_MISMATCH.value,
        supplier_name="Global Tech Ltd",
        invoice_reference="INV-GT-100",
        expected_amount=Decimal("1000.00"),
        invoiced_amount=Decimal("1250.00"),
        potential_difference=Decimal("250.00"),
        severity=Severity.HIGH.value,
        review_status=ReviewStatus.NEW.value,
        calculation_explanation="Unit price discrepancy",
        rule_version=1
    )
    db_session.add(finding)
    db_session.commit()

    # 1. Human reviewer inspects finding details
    r_get = client.get(f"/v1/findings/{finding.id}", headers=headers)
    assert r_get.status_code == status.HTTP_200_OK
    assert r_get.json()["review_status"] == ReviewStatus.NEW.value

    # 2. Human reviewer approves finding with comments
    decision_payload = {
        "action": "CONFIRM",
        "comment": "Confirmed against contract amendment #2 - rate of £10 was agreed."
    }
    r_decide = client.post(f"/v1/findings/{finding.id}/decisions", json=decision_payload, headers=headers)
    assert r_decide.status_code == status.HTTP_200_OK
    data = r_decide.json()
    assert data["review_status"] == ReviewStatus.CONFIRMED.value
    assert len(data["decisions"]) == 1
    assert data["decisions"][0]["action"] == "CONFIRM"
    assert "amendment" in data["decisions"][0]["comment"]

    # 3. Reject finding via PATCH
    r_patch = client.patch(
        f"/v1/findings/{finding.id}",
        json={"review_status": "REJECTED", "comment": "Supplier issued a waiver credit previously."},
        headers=headers
    )
    assert r_patch.status_code == status.HTTP_200_OK
    assert r_patch.json()["review_status"] == ReviewStatus.REJECTED.value

