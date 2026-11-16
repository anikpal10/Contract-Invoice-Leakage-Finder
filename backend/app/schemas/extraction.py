from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date
from decimal import Decimal

class ExtractedFieldResponse(BaseModel):
    id: str
    field_name: str
    extracted_value: Optional[str] = None
    source_page_or_cell: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    extraction_method: str
    requires_review: bool
    reviewed_value: Optional[str] = None

    class Config:
        from_attributes = True

class ExtractedFieldUpdate(BaseModel):
    reviewed_value: str

class ContractLineItemSchema(BaseModel):
    item_code: Optional[str] = None
    description: str
    contracted_unit_price: Decimal
    unit_of_measure: str = "EA"
    min_quantity: Optional[Decimal] = Decimal("0")
    tier_discount_pct: Optional[Decimal] = Decimal("0")
    source_page_or_row: Optional[str] = None
    confidence: Optional[Decimal] = None

class POLineItemSchema(BaseModel):
    line_number: Optional[int] = None
    item_code: Optional[str] = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    source_page_or_row: Optional[str] = None
    confidence: Optional[Decimal] = None

class InvoiceLineItemSchema(BaseModel):
    line_number: Optional[int] = None
    item_code: Optional[str] = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    tax_rate: Optional[Decimal] = Decimal("20.0")
    source_page_or_row: Optional[str] = None
    confidence: Optional[Decimal] = None

class GRNLineItemSchema(BaseModel):
    item_code: Optional[str] = None
    description: str
    quantity_received: Decimal
    source_page_or_row: Optional[str] = None
    confidence: Optional[Decimal] = None

