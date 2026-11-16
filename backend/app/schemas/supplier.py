from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class SupplierCreate(BaseModel):
    name: str
    supplier_code: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: Optional[str] = "30 Days Net"
    contact_email: Optional[EmailStr] = None

class SupplierResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    canonical_name: str
    supplier_code: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: Optional[str] = None
    contact_email: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

