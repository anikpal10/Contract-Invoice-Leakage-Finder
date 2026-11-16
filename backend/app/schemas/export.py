from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class ExportRequest(BaseModel):
    format: str  # "CSV" or "PDF"
    include_rejected: bool = False

class ExportRecordResponse(BaseModel):
    id: str
    case_id: str
    format: str
    file_name: str
    record_count: int
    total_leakage_amount: Decimal
    created_at: datetime
    download_url: Optional[str] = None

    class Config:
        from_attributes = True

