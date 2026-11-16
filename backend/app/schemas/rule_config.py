from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class RuleConfigCreate(BaseModel):
    price_variance_tolerance_pct: Decimal = Decimal("0.00")
    price_variance_tolerance_abs: Decimal = Decimal("0.00")
    quantity_variance_tolerance_pct: Decimal = Decimal("0.00")
    duplicate_window_days: int = 90
    fuzzy_match_threshold: int = 85
    high_severity_threshold: Decimal = Decimal("500.00")
    critical_severity_threshold: Decimal = Decimal("2500.00")
    require_grn_for_goods: bool = True
    change_reason: Optional[str] = "Updated admin configuration"

class RuleConfigResponse(BaseModel):
    id: str
    organization_id: str
    version: int
    is_active: bool
    price_variance_tolerance_pct: Decimal
    price_variance_tolerance_abs: Decimal
    quantity_variance_tolerance_pct: Decimal
    duplicate_window_days: int
    fuzzy_match_threshold: int
    high_severity_threshold: Decimal
    critical_severity_threshold: Decimal
    require_grn_for_goods: bool
    change_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

