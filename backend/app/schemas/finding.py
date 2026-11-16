from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

class ReviewDecisionResponse(BaseModel):
    id: str
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    action: str
    previous_status: str
    new_status: str
    comment: Optional[str] = None
    adjusted_amount: Optional[Decimal] = None
    created_at: datetime

    class Config:
        from_attributes = True

class FindingResponse(BaseModel):
    id: str
    case_id: str
    finding_category: str
    supplier_name: str
    invoice_reference: str
    line_number: Optional[int] = None
    item_code: Optional[str] = None
    item_description: Optional[str] = None
    expected_amount: Decimal
    invoiced_amount: Decimal
    potential_difference: Decimal
    currency: str
    severity: str
    review_status: str
    calculation_explanation: str
    source_document_references: Optional[List[Dict[str, Any]]] = None
    rule_version: int
    requires_more_info_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    decisions: Optional[List[ReviewDecisionResponse]] = []

    class Config:
        from_attributes = True

class FindingReviewAction(BaseModel):
    action: str  # CONFIRM, REJECT, REQUEST_INFO, COMMENT
    comment: Optional[str] = None
    adjusted_amount: Optional[Decimal] = None

class FindingPatchRequest(BaseModel):
    review_status: Optional[str] = None
    comment: Optional[str] = None
    adjusted_amount: Optional[Decimal] = None

