from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

class CaseCreate(BaseModel):
    workspace_id: str
    supplier_id: Optional[str] = None
    title: str
    currency: Optional[str] = "GBP"
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    notes: Optional[str] = None

class CaseResponse(BaseModel):
    id: str
    organization_id: str
    workspace_id: str
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    title: str
    case_reference: str
    currency: str
    status: str
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    document_count: Optional[int] = 0
    finding_count: Optional[int] = 0
    potential_leakage_amount: Optional[Decimal] = Decimal("0.00")
    confirmed_leakage_amount: Optional[Decimal] = Decimal("0.00")

    class Config:
        from_attributes = True

class CaseSummaryStats(BaseModel):
    total_invoices: int
    total_cases: int
    total_documents: Optional[int] = 0
    potential_leakage: Decimal          # sum of NEW findings only
    confirmed_leakage_amount: Decimal = Decimal("0.00")  # sum of CONFIRMED findings
    findings_awaiting_review: int
    confirmed_findings: int
    rejected_findings: int

class CaseAnalyticsResponse(BaseModel):
    total_invoices_analyzed: int
    total_discrepancies: int
    total_potential_leakage: float
    confirmed_leakage: float
    category_breakdown: dict
    severity_breakdown: dict
    top_leakage_suppliers: List[dict]

