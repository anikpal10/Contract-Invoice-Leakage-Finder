from decimal import Decimal
import pytest
from backend.app.models.case import ReconciliationCase
from backend.app.models.document import UploadedDocument, ProcessingStatus
from backend.app.models.extracted_entities import Contract, ContractLineItem, Invoice, InvoiceLineItem
from backend.app.models.finding import Finding, FindingCategory
from backend.app.services.matching import matching_service
from backend.app.services.reconciliation_engine import reconciliation_engine
from backend.app.services.financial_summary import deduplicate_findings_for_financial_summary

def test_contract_matching_isolation_prevents_false_cross_contract_findings(db_session, test_tenants):
    """
    Test Requirement 6: Verify the ₹9,600 finding against its original contract and invoice evidence.
    Root cause: Invoices were matched to contracts[0] blindly, causing Apex's INV-2026-4412 to match
    Sunrise's CON-2026-031, falsely comparing Pressure Gauge PG-40 (1,400) against Safety Gloves (200)
    due to shared synthetic code ITEM-04, resulting in 8 * (1400 - 200) = 9,600.
    With proper contract matching by reference and supplier, PG-40 matches CON-2026-044 at 1,250,
    yielding a true variance of 8 * (1400 - 1250) = 1,200.
    """
    org = test_tenants["org1"]
    ws = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Multi-Contract Audit",
        case_reference="CASE-AUDIT-001",
        currency="INR"
    )
    db_session.add(case)
    db_session.flush()

    # Contract 1: Sunrise Industrial Components (CON-2026-031) - Added first to be contracts[0]
    c1 = Contract(
        case_id=case.id,
        document_id="doc_c1",
        contract_reference="CON-2026-031",
        supplier_name="Sunrise Industrial Components",
        currency="INR"
    )
    db_session.add(c1)
    db_session.flush()

    cli1_1 = ContractLineItem(
        contract_id=c1.id,
        item_code="ITEM-01",
        description="Industrial Valve Type A",
        contracted_unit_price=Decimal("2500.00")
    )
    cli1_4 = ContractLineItem(
        contract_id=c1.id,
        item_code="ITEM-04",
        description="Safety Gloves (pair)",
        contracted_unit_price=Decimal("200.00")
    )
    db_session.add_all([cli1_1, cli1_4])

    # Contract 2: Apex Industrial Supplies (CON-2026-044)
    c2 = Contract(
        case_id=case.id,
        document_id="doc_c2",
        contract_reference="CON-2026-044",
        supplier_name="Apex Industrial Supplies",
        currency="INR"
    )
    db_session.add(c2)
    db_session.flush()

    cli2_1 = ContractLineItem(
        contract_id=c2.id,
        item_code="ITEM-01",
        description="Industrial Motor Bearing MB-20",
        contracted_unit_price=Decimal("1500.00")
    )
    cli2_4 = ContractLineItem(
        contract_id=c2.id,
        item_code="ITEM-04",
        description="Pressure Gauge PG-40",
        contracted_unit_price=Decimal("1250.00")
    )
    db_session.add_all([cli2_1, cli2_4])
    db_session.flush()

    # Invoice: Apex Industrial Supplies (INV-2026-4412)
    inv = Invoice(
        case_id=case.id,
        document_id="doc_inv_apex",
        invoice_number="INV-2026-4412",
        contract_reference="CON-2026-044",
        supplier_name="Apex Industrial Supplies",
        currency="INR",
        subtotal=Decimal("27700.00"),
        total_amount=Decimal("27700.00")
    )
    db_session.add(inv)
    db_session.flush()

    inv_line1 = InvoiceLineItem(
        invoice_id=inv.id,
        item_code="ITEM-01",
        description="Industrial Motor Bearing MB-20",
        quantity=Decimal("10.00"),
        unit_price=Decimal("1650.00"),
        line_total=Decimal("16500.00")
    )
    inv_line4 = InvoiceLineItem(
        invoice_id=inv.id,
        item_code="ITEM-04",
        description="Pressure Gauge PG-40",
        quantity=Decimal("8.00"),
        unit_price=Decimal("1400.00"),
        line_total=Decimal("11200.00")
    )
    db_session.add_all([inv_line1, inv_line4])
    db_session.commit()

    # Verify matching service picks CON-2026-044, NOT contracts[0] CON-2026-031
    all_contracts = [c1, c2]
    matched_contract = matching_service.match_invoice_to_contract(inv, all_contracts, db_session)
    assert matched_contract is not None
    assert matched_contract.contract_reference == "CON-2026-044"
    assert matched_contract.supplier_name == "Apex Industrial Supplies"

    # Run reconciliation engine
    findings = reconciliation_engine.run_reconciliation(db_session, case, reset_reviewed=True)

    # We should have exactly 2 findings:
    # 1. Industrial Motor Bearing MB-20: 10 * (1650 - 1500) = 1,500
    # 2. Pressure Gauge PG-40: 8 * (1400 - 1250) = 1,200 (NOT 9,600!)
    assert len(findings) == 2

    findings_by_item = {f.item_description: f for f in findings}
    assert "Pressure Gauge PG-40" in findings_by_item
    pg_finding = findings_by_item["Pressure Gauge PG-40"]
    assert pg_finding.potential_difference == Decimal("1200.00")
    assert pg_finding.expected_amount == Decimal("10000.00")  # 8 * 1250
    assert pg_finding.invoiced_amount == Decimal("11200.00")  # 8 * 1400

    assert "Industrial Motor Bearing MB-20" in findings_by_item
    mb_finding = findings_by_item["Industrial Motor Bearing MB-20"]
    assert mb_finding.potential_difference == Decimal("1500.00")
    assert mb_finding.expected_amount == Decimal("15000.00")  # 10 * 1500
    assert mb_finding.invoiced_amount == Decimal("16500.00")  # 10 * 1650

def test_missing_subtotal_never_treated_as_zero(db_session, test_tenants):
    """
    Test Requirements 3 & 4:
    - Never treat a missing subtotal as zero.
    - Calculate billed amounts from validated extracted line items.
    """
    org = test_tenants["org1"]
    ws = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Missing Subtotal Test",
        case_reference="CASE-SUBTOTAL-001",
        currency="INR"
    )
    db_session.add(case)
    db_session.flush()

    # Test ExtractionService derives subtotal from line items when raw subtotal is missing/None
    from backend.app.services.extraction import ExtractionService
    extractor = ExtractionService()
    raw_data = {
        "invoice_number": "INV-NO-SUBTOTAL-01",
        "supplier_name": "Quality Spares Ltd",
        "currency": "INR",
        "subtotal": None,  # Missing subtotal
        "total_amount": None,
        "line_items": [
            {
                "line_number": 1,
                "description": "Gear Assembly",
                "quantity": 5.0,
                "unit_price": 1000.0,
                "line_total": 5000.0
            },
            {
                "line_number": 2,
                "description": "Hydraulic Seal",
                "quantity": 10.0,
                "unit_price": 200.0,
                "line_total": 2000.0
            }
        ]
    }

    doc = UploadedDocument(
        case_id=case.id,
        organization_id=org.id,
        filename="missing_subtotal.pdf",
        original_filename="missing_subtotal.pdf",
        category="INVOICE",
        file_type="pdf",
        file_size_bytes=1024,
        sha256_hash="dummy_hash_1",
        processing_status=ProcessingStatus.EXTRACTED.value,
        storage_path="storage/dummy.pdf"
    )
    db_session.add(doc)
    db_session.flush()

    extractor._persist_entities(db_session, doc, raw_data, method="TEST_PARSER")
    db_session.commit()

    saved_inv = db_session.query(Invoice).filter(Invoice.document_id == doc.id).first()
    assert saved_inv is not None
    # Derived subtotal must be 5000 + 2000 = 7000.00, NOT 0.00!
    assert saved_inv.subtotal == Decimal("7000.00")
    assert saved_inv.total_amount == Decimal("7000.00")

    findings = reconciliation_engine.run_reconciliation(db_session, case, reset_reviewed=True)

    # Should NOT generate INCORRECT_INVOICE_TOTAL because subtotal was derived from lines (7,000.00)
    invoice_math_findings = [f for f in findings if f.finding_category == FindingCategory.INCORRECT_INVOICE_TOTAL.value]
    assert len(invoice_math_findings) == 0

def test_deduplicate_findings_prevents_aggregate_and_child_double_counting():
    """
    Test Requirement 5: Prevent aggregate and child findings from being counted twice.
    When both an aggregate header total mismatch (e.g. 58,000) and child line total mismatches
    (e.g. 33,000 + 25,000) exist for the same invoice, deduplication must exclude the aggregate.
    """
    findings = [
        Finding(
            id="f_hdr",
            invoice_reference="INV-TEST-001",
            finding_category=FindingCategory.INCORRECT_INVOICE_TOTAL.value,
            potential_difference=Decimal("58000.00"),
            currency="INR",
            review_status="NEW"
        ),
        Finding(
            id="f_line1",
            invoice_reference="INV-TEST-001",
            finding_category=FindingCategory.INCORRECT_LINE_TOTAL.value,
            item_description="Industrial Valve Type A",
            potential_difference=Decimal("33000.00"),
            currency="INR",
            review_status="NEW"
        ),
        Finding(
            id="f_line2",
            invoice_reference="INV-TEST-001",
            finding_category=FindingCategory.INCORRECT_LINE_TOTAL.value,
            item_description="Steel Pipe 2-inch",
            potential_difference=Decimal("25000.00"),
            currency="INR",
            review_status="NEW"
        ),
        Finding(
            id="f_price",
            invoice_reference="INV-TEST-001",
            finding_category=FindingCategory.CONTRACT_PRICE_MISMATCH.value,
            item_description="Industrial Valve Type A",
            potential_difference=Decimal("3000.00"),
            currency="INR",
            review_status="NEW"
        )
    ]

    deduped = deduplicate_findings_for_financial_summary(findings)
    # The header arithmetic finding f_hdr must be excluded because f_line1 and f_line2 exist
    deduped_ids = {f.id for f in deduped}
    assert "f_hdr" not in deduped_ids
    assert "f_line1" in deduped_ids
    assert "f_line2" in deduped_ids
    assert "f_price" in deduped_ids

def test_unvalidated_document_does_not_show_financial_summary(db_session, test_tenants):
    """
    Test Requirement 7: Never show a final financial summary when required source data is missing or unvalidated.
    """
    from backend.app.api.v1.documents import _assemble_pipeline_result

    org = test_tenants["org1"]
    ws = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Unvalidated Doc Case",
        case_reference="CASE-UNVAL-001",
        currency="INR"
    )
    db_session.add(case)
    db_session.flush()

    # Document with FAILED or UNVALIDATED status
    failed_doc = UploadedDocument(
        case_id=case.id,
        organization_id=org.id,
        filename="corrupted_scan.pdf",
        original_filename="corrupted_scan.pdf",
        category="INVOICE",
        file_type="pdf",
        file_size_bytes=1024,
        sha256_hash="dummy_hash_2",
        processing_status=ProcessingStatus.FAILED.value,
        storage_path="storage/dummy.pdf"
    )
    db_session.add(failed_doc)
    db_session.commit()

    pipeline_res = _assemble_pipeline_result(failed_doc, case, db_session)
    assert pipeline_res.currency_status == "UNVALIDATED"
    assert pipeline_res.reconciled is False
    assert pipeline_res.recognized_data.get("total_amount") is None
    assert pipeline_res.recognized_data.get("subtotal") is None
    assert len(pipeline_res.recognized_data.get("line_items", [])) == 0
    assert pipeline_res.findings_count == 0
    assert pipeline_res.potential_leakage == Decimal("0.00")


def test_undercharge_detected_and_classified_as_potential_undercharge(db_session, test_tenants):
    """
    Regression test for INR case CON-2026-071 / INV-2026-7104.

    Pressure Gauge PG-40: contract rate 2,500, invoice rate 2,375, quantity 4.
    Expected variance = 4 * (2375 - 2500) = -500 (an undercharge, NOT an overcharge).

    The engine must emit a POTENTIAL_UNDERCHARGE finding with a negative
    potential_difference and evidence citations for BOTH the contract and invoice.
    """
    org = test_tenants["org1"]
    ws = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="INR Undercharge Audit",
        case_reference="CON-2026-071",
        currency="INR"
    )
    db_session.add(case)
    db_session.flush()

    contract = Contract(
        case_id=case.id,
        document_id="doc_contract_071",
        contract_reference="CON-2026-071",
        supplier_name="Precision Instruments Pvt Ltd",
        currency="INR"
    )
    db_session.add(contract)
    db_session.flush()

    contract_line = ContractLineItem(
        contract_id=contract.id,
        item_code="PG-40",
        description="Pressure Gauge PG-40",
        contracted_unit_price=Decimal("2500.00")
    )
    db_session.add(contract_line)
    db_session.flush()

    inv = Invoice(
        case_id=case.id,
        document_id="doc_inv_7104",
        invoice_number="INV-2026-7104",
        contract_reference="CON-2026-071",
        supplier_name="Precision Instruments Pvt Ltd",
        currency="INR",
        subtotal=Decimal("51750.00"),
        total_amount=Decimal("51750.00")
    )
    db_session.add(inv)
    db_session.flush()

    inv_line = InvoiceLineItem(
        invoice_id=inv.id,
        item_code="PG-40",
        description="Pressure Gauge PG-40",
        quantity=Decimal("4.00"),
        unit_price=Decimal("2375.00"),
        line_total=Decimal("9500.00")
    )
    db_session.add(inv_line)
    db_session.commit()

    findings = reconciliation_engine.run_reconciliation(db_session, case, reset_reviewed=True)

    undercharge_findings = [
        f for f in findings
        if f.finding_category == FindingCategory.POTENTIAL_UNDERCHARGE.value
    ]
    assert len(undercharge_findings) == 1, "Expected exactly one undercharge finding for PG-40"

    pg = undercharge_findings[0]
    assert pg.item_code == "PG-40"
    assert pg.potential_difference == Decimal("-500.00")
    assert pg.expected_amount == Decimal("10000.00")   # 4 * 2500
    assert pg.invoiced_amount == Decimal("9500.00")    # 4 * 2375
    assert pg.currency == "INR"

    # Must NOT be classified as an overcharge category
    assert pg.finding_category != FindingCategory.CONTRACT_PRICE_MISMATCH.value

    # Evidence citations must reference BOTH the invoice and the contract
    ref_types = {r.get("type") for r in (pg.source_document_references or []) if isinstance(r, dict)}
    assert "INVOICE" in ref_types
    assert "CONTRACT" in ref_types


def test_financial_summary_separates_gross_overcharges_undercharges_and_net_variance(
    db_session, test_tenants, client
):
    """
    Regression test: gross overcharges and net variance must be reported as
    SEPARATE metrics.

    Scenario (INR):
      - Overcharge: 4 * (2500 - 2000) = +2,000  (contract 2,000, invoice 2,500)
      - Undercharge: 4 * (2375 - 2500) = -500   (contract 2,500, invoice 2,375)
      - Gross overcharges = 2,000
      - Potential undercharges = 500
      - Net variance = 2,000 - 500 = 1,500
    """
    org = test_tenants["org1"]
    ws = test_tenants["ws1"]
    token = test_tenants["token1"]

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Mixed Variance Audit",
        case_reference="CON-2026-071",
        currency="INR"
    )
    db_session.add(case)
    db_session.flush()

    contract = Contract(
        case_id=case.id,
        document_id="doc_contract_mixed",
        contract_reference="CON-2026-071",
        supplier_name="Precision Instruments Pvt Ltd",
        currency="INR"
    )
    db_session.add(contract)
    db_session.flush()

    # Overcharged item: contract 2,000
    c_over = ContractLineItem(
        contract_id=contract.id,
        item_code="OV-10",
        description="Overcharged Widget OV-10",
        contracted_unit_price=Decimal("2000.00")
    )
    # Undercharged item: contract 2,500
    c_under = ContractLineItem(
        contract_id=contract.id,
        item_code="PG-40",
        description="Pressure Gauge PG-40",
        contracted_unit_price=Decimal("2500.00")
    )
    db_session.add_all([c_over, c_under])
    db_session.flush()

    inv = Invoice(
        case_id=case.id,
        document_id="doc_inv_mixed",
        invoice_number="INV-2026-7104",
        contract_reference="CON-2026-071",
        supplier_name="Precision Instruments Pvt Ltd",
        currency="INR",
        subtotal=Decimal("19500.00"),
        total_amount=Decimal("19500.00")
    )
    db_session.add(inv)
    db_session.flush()

    inv_over = InvoiceLineItem(
        invoice_id=inv.id,
        item_code="OV-10",
        description="Overcharged Widget OV-10",
        quantity=Decimal("4.00"),
        unit_price=Decimal("2500.00"),
        line_total=Decimal("10000.00")
    )
    inv_under = InvoiceLineItem(
        invoice_id=inv.id,
        item_code="PG-40",
        description="Pressure Gauge PG-40",
        quantity=Decimal("4.00"),
        unit_price=Decimal("2375.00"),
        line_total=Decimal("9500.00")
    )
    db_session.add_all([inv_over, inv_under])
    db_session.commit()

    reconciliation_engine.run_reconciliation(db_session, case, reset_reviewed=True)

    resp = client.get(
        "/v1/cases/summary/dashboard",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert Decimal(str(data["gross_overcharges"])) == Decimal("2000.00")
    assert Decimal(str(data["potential_undercharges"])) == Decimal("500.00")
    assert Decimal(str(data["net_variance"])) == Decimal("1500.00")

    # Gross overcharges and net variance must remain distinct metrics
    assert Decimal(str(data["gross_overcharges"])) != Decimal(str(data["net_variance"]))
