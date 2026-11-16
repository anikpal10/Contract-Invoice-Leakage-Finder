from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user
from backend.app.models.user import User
from backend.app.models.audit_log import AuditLog

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

class AuditLogItemResponse(BaseModel):
    id: str
    organization_id: str
    user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: str
    payload_before: Optional[dict] = None
    payload_after: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=List[AuditLogItemResponse])
def get_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logs = db.query(AuditLog).filter(
        AuditLog.organization_id == current_user.organization_id
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return logs

