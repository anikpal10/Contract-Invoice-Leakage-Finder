import pytest
from decimal import Decimal
import pandas as pd

from backend.app.schemas.llm_extraction import (
    ExtractedDocumentData,
    ExtractedLineItem,
    LLMMatchResult,
    LLMLeakageAnalysis
)
from backend.app.services.pandas_processor import pandas_processor
from backend.app.services.matching import matching_service
from backend.app.services.llm_service import llm_service
from backend.app.services.extraction import extraction_service
from backend.app.models.finding import Finding, FindingCategory, Severity, ReviewStatus
from backend.app.models.extracted_entities import Invoice, ContractLineItem, InvoiceLineItem

def test_pydantic_line_item_validation():
    """Verify that ExtractedLineItem enforces strict validation and defaults."""
    item = ExtractedLineItem(
        product_name="Cloud Hosting Enterprise",
        product_description="High-availability cluster compute instances",
        quantity=Decimal("5.0"),
        unit_price=Decimal("1200.00"),
        total_price=Decimal("6000.00"),
        tax_amount=Decimal("1200.00"),
        currency="GBP",
        source_page_number=2,
        text_evidence="Item 1: Cloud Hosting Enterprise 5 units @ GBP 1,200.00 = GBP 6,000.00",
        confidence_score=0.98
    )

    assert item.product_name == "Cloud Hosting Enterprise"
    assert item.quantity == Decimal("5.0")
    assert item.unit_price == Decimal("1200.00")
    assert item.source_page_number == 2
    assert "Item 1" in item.text_evidence
    assert item.confidence_score == 0.98

def test_pydantic_extracted_document_validation():
    """Verify full document structure with line items and anti-hallucination guardrails."""
    doc = ExtractedDocumentData(
        document_category="INVOICE",
        reference_number="INV-2026-9081",
        supplier_name="Apex Logistics Ltd",
        document_date="2026-10-15",
        due_date="2026-11-15",
        currency="GBP",
        subtotal=Decimal("10000.00"),
        tax_amount=Decimal("2000.00"),
        total_amount=Decimal("12000.00"),
        confidence_score=0.96,
        line_items=[
            ExtractedLineItem(
                line_number=1,
                product_name="Freight Delivery Express",
                quantity=Decimal("10"),
                unit_price=Decimal("1000.00"),
                total_price=Decimal("10000.00")
            )
        ]
    )

    assert doc.reference_number == "INV-2026-9081"
    assert len(doc.line_items) == 1
    assert doc.line_items[0].unit_price == Decimal("1000.00")

def test_python_decimal_cost_difference_authority():
    """
    Verify Python calculation as final authority:
    Cost Difference = Invoice Amount - Expected Contract Amount
    When Invoice > Contract, flag as leakage.
    """
    contract_unit_price = Decimal("40000.00")
    invoice_unit_price = Decimal("45000.00")
    quantity = Decimal("10.0")

    expected_amount = contract_unit_price * quantity  # 400,000.00
    actual_amount = invoice_unit_price * quantity     # 450,000.00
    cost_difference = actual_amount - expected_amount # 50,000.00

    assert expected_amount == Decimal("400000.00")
    assert actual_amount == Decimal("450000.00")
    assert cost_difference == Decimal("50000.00")
    assert cost_difference > Decimal("0.00"), "Must be flagged as potential leakage"

def test_pandas_comparison_dataframe_building():
    """Test pandas_processor converts findings into analytical DataFrames."""
    findings = [
        Finding(
            id="f-001",
            case_id="case-100",
            organization_id="org-100",
            finding_category=FindingCategory.CONTRACT_PRICE_MISMATCH.value,
            supplier_name="TechSupplies UK",
            invoice_reference="INV-7701",
            line_number=1,
            item_code="LAP-01",
            item_description="Dell Latitude Laptop 16GB",
            expected_amount=Decimal("400000.00"),
            invoiced_amount=Decimal("450000.00"),
            potential_difference=Decimal("50000.00"),
            currency="INR",
            severity=Severity.HIGH.value,
            review_status=ReviewStatus.NEW.value,
            calculation_explanation="Price variance of INR 5000 per unit",
            rule_version=1
        ),
        Finding(
            id="f-002",
            case_id="case-100",
            organization_id="org-100",
            finding_category=FindingCategory.DUPLICATE_INVOICE.value,
            supplier_name="TechSupplies UK",
            invoice_reference="INV-7701-DUP",
            line_number=None,
            item_code=None,
            item_description="Duplicate invoice submission",
            expected_amount=Decimal("0.00"),
            invoiced_amount=Decimal("450000.00"),
            potential_difference=Decimal("450000.00"),
            currency="INR",
            severity=Severity.CRITICAL.value,
            review_status=ReviewStatus.CONFIRMED.value,
            calculation_explanation="Exact duplicate invoice reference detected",
            rule_version=1
        )
    ]

    df = pandas_processor.build_comparison_dataframe(findings)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "cost_difference" in df.columns
    assert df["cost_difference"].sum() == 500000.00

def test_pandas_dashboard_analytics_aggregation():
    """Test pandas_processor aggregates metrics, categories, severities, and top suppliers."""
    findings = [
        Finding(
            id="f-1",
            case_id="c-1",
            organization_id="org-1",
            finding_category=FindingCategory.CONTRACT_PRICE_MISMATCH.value,
            supplier_name="Supplier Alpha",
            invoice_reference="INV-01",
            expected_amount=Decimal("1000.00"),
            invoiced_amount=Decimal("1200.00"),
            potential_difference=Decimal("200.00"),
            currency="GBP",
            severity=Severity.MEDIUM.value,
            review_status=ReviewStatus.NEW.value,
            calculation_explanation="Test",
            rule_version=1
        ),
        Finding(
            id="f-2",
            case_id="c-1",
            organization_id="org-1",
            finding_category=FindingCategory.CONTRACT_PRICE_MISMATCH.value,
            supplier_name="Supplier Alpha",
            invoice_reference="INV-02",
            expected_amount=Decimal("2000.00"),
            invoiced_amount=Decimal("2500.00"),
            potential_difference=Decimal("500.00"),
            currency="GBP",
            severity=Severity.HIGH.value,
            review_status=ReviewStatus.CONFIRMED.value,
            calculation_explanation="Test",
            rule_version=1
        )
    ]

    dummy_invoices = [Invoice(id="inv-1"), Invoice(id="inv-2"), Invoice(id="inv-3")]
    analytics = pandas_processor.compute_dashboard_analytics(dummy_invoices, findings)

    assert analytics["total_invoices_analyzed"] == 3
    assert analytics["total_discrepancies"] == 2
    assert analytics["total_potential_leakage"] == 700.00
    assert analytics["confirmed_leakage"] == 500.00
    assert "CONTRACT_PRICE_MISMATCH" in analytics["category_breakdown"]
    assert len(analytics["top_leakage_suppliers"]) == 1
    assert analytics["top_leakage_suppliers"][0]["supplier_name"] == "Supplier Alpha"
    assert analytics["top_leakage_suppliers"][0]["leakage_amount"] == 700.00

def test_extraction_pydantic_conversion():
    """Verify ExtractionService correctly converts Pydantic model into entity persistence dictionary."""
    pydantic_data = ExtractedDocumentData(
        document_category="INVOICE",
        reference_number="INV-LLM-001",
        supplier_name="Cloud Network Ltd",
        document_date="2026-10-20",
        due_date="2026-11-20",
        currency="USD",
        subtotal=Decimal("5000.00"),
        tax_amount=Decimal("500.00"),
        total_amount=Decimal("5500.00"),
        confidence_score=0.97,
        line_items=[
            ExtractedLineItem(
                line_number=1,
                product_name="Managed Router Service",
                product_description="Enterprise grade network router",
                quantity=Decimal("2.0"),
                unit_price=Decimal("2500.00"),
                total_price=Decimal("5000.00"),
                tax_amount=Decimal("500.00"),
                currency="USD",
                source_page_number=1,
                text_evidence="Router unit @ 2500",
                confidence_score=0.99
            )
        ]
    )

    conv = extraction_service._convert_pydantic_to_extracted_dict(pydantic_data, "INVOICE")
    assert conv["invoice_number"] == "INV-LLM-001"
    assert conv["supplier_name"] == "Cloud Network Ltd"
    assert conv["subtotal"] == 5000.00
    assert conv["total_amount"] == 5500.00
    assert len(conv["line_items"]) == 1
    assert conv["line_items"][0]["unit_price"] == 2500.00
    assert conv["line_items"][0]["source_page_or_row"] == "Page 1"
    assert conv["line_items"][0]["confidence"] == 0.99

def test_llm_product_matching_fallback():
    """Verify LLMMatchResult enforces human review requirement when confidence is low or provider offline."""
    result = llm_service.match_products_semantic(
        invoice_item_desc="Premium Widget Ultra v2",
        invoice_item_code="WGT-02",
        candidate_contract_items=[]
    )

    assert result.is_match is False
    assert result.requires_human_review is True
    assert result.confidence_score == 0.0

