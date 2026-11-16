from decimal import Decimal
from datetime import date
from backend.app.models.case import ReconciliationCase
from backend.app.models.rule_config import RuleConfiguration
from backend.app.models.extracted_entities import (
    Contract, ContractLineItem,
    PurchaseOrder, POLineItem,
    Invoice, InvoiceLineItem,
    GoodsReceivedNote, GRNLineItem
)
from backend.app.models.finding import FindingCategory, Severity, ReviewStatus
from backend.app.services.reconciliation_engine import reconciliation_engine

def test_contract_price_mismatch_detection(db_session, test_tenants):
    org = test_tenants["org1"]
    ws = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Test Reconciliation Case",
        case_reference="CASE-TEST-001",
        currency="GBP"
    )
    db_session.add(case)
    db_session.flush()

    # Contract: Unit price £50.00
    contract = Contract(
        case_id=case.id,
        document_id="doc_ctr_1",
        contract_reference="CTR-ABC-2026",
        supplier_name="ABC Supplies",
        currency="GBP"
    )
    db_session.add(contract)
    db_session.flush()

    cli = ContractLineItem(
        contract_id=contract.id,
        item_code="ITM-WIDGET-01",
        description="Premium Steel Widget",
        contracted_unit_price=Decimal("50.00"),
        unit_of_measure="EA"
    )
    db_session.add(cli)

    # PO: Unit price £50.00, Quantity 100
    po = PurchaseOrder(
        case_id=case.id,
        document_id="doc_po_1",
        po_number="PO-99001",
        supplier_name="ABC Supplies",
        currency="GBP"
    )
    db_session.add(po)
    db_session.flush()

    poli = POLineItem(
        po_id=po.id,
        line_number=1,
        item_code="ITM-WIDGET-01",
        description="Premium Steel Widget",
        quantity=Decimal("100.00"),
        unit_price=Decimal("50.00"),
        line_total=Decimal("5000.00")
    )
    db_session.add(poli)

    # Invoice: Overbilled at £55.00 for 100 units = £5,500
    inv = Invoice(
        case_id=case.id,
        document_id="doc_inv_1",
        invoice_number="INV-2026-001",
        supplier_name="ABC Supplies",
        po_reference="PO-99001",
        currency="GBP",
        subtotal=Decimal("5500.00"),
        tax_amount=Decimal("1100.00"),
        total_amount=Decimal("6600.00")
    )
    db_session.add(inv)
    db_session.flush()

    ili = InvoiceLineItem(
        invoice_id=inv.id,
        line_number=1,
        item_code="ITM-WIDGET-01",
        description="Premium Steel Widget",
        quantity=Decimal("100.00"),
        unit_price=Decimal("55.00"),
        line_total=Decimal("5500.00")
    )
    db_session.add(ili)
    db_session.commit()

    findings = reconciliation_engine.run_reconciliation(db_session, case)
    
    assert len(findings) >= 1
    # Check that contract price mismatch was caught
    contract_finding = next((f for f in findings if f.finding_category == FindingCategory.CONTRACT_PRICE_MISMATCH.value), None)
    assert contract_finding is not None
    assert contract_finding.expected_amount == Decimal("5000.00")
    assert contract_finding.invoiced_amount == Decimal("5500.00")
    assert contract_finding.potential_difference == Decimal("500.00")
    assert contract_finding.review_status == ReviewStatus.NEW.value

def test_quantity_exceeding_ordered_detection(db_session, test_tenants):
    org = test_tenants["org1"]
    ws = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Qty Test Case",
        case_reference="CASE-QTY-001"
    )
    db_session.add(case)
    db_session.flush()

    # PO ordered 50 units @ £20
    po = PurchaseOrder(
        case_id=case.id,
        document_id="doc_po_2",
        po_number="PO-QTY-50",
        supplier_name="Acme Tools"
    )
    db_session.add(po)
    db_session.flush()

    poli = POLineItem(
        po_id=po.id,
        line_number=1,
        item_code="TOOL-01",
        description="Heavy Duty Drill",
        quantity=Decimal("50.00"),
        unit_price=Decimal("20.00"),
        line_total=Decimal("1000.00")
    )
    db_session.add(poli)

    # Invoice billed 70 units @ £20 (excess 20 units)
    inv = Invoice(
        case_id=case.id,
        document_id="doc_inv_2",
        invoice_number="INV-QTY-70",
        supplier_name="Acme Tools",
        po_reference="PO-QTY-50",
        subtotal=Decimal("1400.00"),
        total_amount=Decimal("1400.00")
    )
    db_session.add(inv)
    db_session.flush()

    ili = InvoiceLineItem(
        invoice_id=inv.id,
        line_number=1,
        item_code="TOOL-01",
        description="Heavy Duty Drill",
        quantity=Decimal("70.00"),
        unit_price=Decimal("20.00"),
        line_total=Decimal("1400.00")
    )
    db_session.add(ili)
    db_session.commit()

    findings = reconciliation_engine.run_reconciliation(db_session, case)
    qty_finding = next((f for f in findings if f.finding_category == FindingCategory.QUANTITY_OVER_PO.value), None)
    assert qty_finding is not None
    assert qty_finding.expected_amount == Decimal("1000.00")
    assert qty_finding.invoiced_amount == Decimal("1400.00")
    assert qty_finding.potential_difference == Decimal("400.00")

def test_duplicate_invoice_detection(db_session, test_tenants):
    org = test_tenants["org1"]
    ws = test_tenants["ws1"]

    case = ReconciliationCase(
        organization_id=org.id,
        workspace_id=ws.id,
        title="Duplicate Test Case",
        case_reference="CASE-DUP-001"
    )
    db_session.add(case)
    db_session.flush()

    # Invoice 1
    inv1 = Invoice(
        case_id=case.id,
        document_id="doc_inv_orig",
        invoice_number="INV-DUP-999",
        supplier_name="Alpha Logistics",
        subtotal=Decimal("2000.00"),
        total_amount=Decimal("2000.00")
    )
    # Invoice 2 - Identical supplier & invoice number
    inv2 = Invoice(
        case_id=case.id,
        document_id="doc_inv_dup",
        invoice_number="INV-DUP-999",
        supplier_name="Alpha Logistics",
        subtotal=Decimal("2000.00"),
        total_amount=Decimal("2000.00")
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()

    findings = reconciliation_engine.run_reconciliation(db_session, case)
    dup_finding = next((f for f in findings if f.finding_category == FindingCategory.DUPLICATE_INVOICE.value), None)
    assert dup_finding is not None
    assert dup_finding.potential_difference == Decimal("2000.00")
    assert dup_finding.severity == Severity.CRITICAL.value or dup_finding.severity == Severity.HIGH.value

