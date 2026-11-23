from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal

class ExtractedLineItem(BaseModel):
    line_number: Optional[int] = None
    product_name: str = Field(description="Product or service name")
    product_description: Optional[str] = Field(default=None, description="Detailed product description or specifications")
    quantity: Decimal = Field(default=Decimal("1.0"), description="Quantity ordered or billed")
    unit_price: Decimal = Field(description="Unit price agreed or billed")
    total_price: Optional[Decimal] = Field(default=None, description="Line total price")
    tax_amount: Optional[Decimal] = Field(default=None, description="Tax amount for this line")
    discount: Optional[Decimal] = Field(default=None, description="Discount amount or percentage if specified")
    currency: Optional[str] = Field(default=None, description="Currency ISO code")
    source_page_number: Optional[int] = Field(default=1, description="Source page number in the document")
    text_evidence: Optional[str] = Field(default=None, description="Exact snippet or sentence from document verifying this item")
    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0, description="Extraction confidence score")

class ExtractedDocumentData(BaseModel):
    document_category: str = Field(default="INVOICE", description="CONTRACT, INVOICE, PURCHASE_ORDER, or GOODS_RECEIVED_NOTE")
    reference_number: Optional[str] = Field(default="REF-UNKNOWN", description="Invoice number, PO number, or Contract reference")
    supplier_name: Optional[str] = Field(default="Unknown Supplier", description="Supplier or vendor name")
    document_date: Optional[str] = Field(default=None, description="Issue date YYYY-MM-DD")
    due_date: Optional[str] = Field(default=None, description="Payment due date YYYY-MM-DD")
    contract_validity_start: Optional[str] = Field(default=None, description="Contract effective start date YYYY-MM-DD")
    contract_validity_end: Optional[str] = Field(default=None, description="Contract expiry date YYYY-MM-DD")
    payment_terms: Optional[str] = Field(default=None, description="Payment terms e.g. Net 30, Due upon receipt")
    currency: Optional[str] = Field(default="REVIEW_REQUIRED", description="Document currency")
    subtotal: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    po_reference: Optional[str] = None
    contract_reference: Optional[str] = None
    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0)
    line_items: List[ExtractedLineItem] = Field(default_factory=list)

class LLMMatchResult(BaseModel):
    is_match: bool
    invoice_item_description: str
    contract_item_description: Optional[str] = None
    matched_contract_line_id: Optional[str] = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    requires_human_review: bool

class LLMLeakageAnalysis(BaseModel):
    discrepancy_type: str
    product_name: str
    contract_unit_price: Decimal
    invoice_unit_price: Decimal
    quantity: Decimal
    expected_amount: Decimal
    actual_amount: Decimal
    cost_difference: Decimal
    explanation: str
    supporting_evidence: str
    confidence_score: float
    requires_human_review: bool
