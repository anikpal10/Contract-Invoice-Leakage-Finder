from typing import Optional, Any
from sqlalchemy.orm import Session
from backend.app.models.audit_log import AuditLog

def log_audit_event(
    db: Session,
    organization_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    user_id: Optional[str] = None,
    payload_before: Optional[Any] = None,
    payload_after: Optional[Any] = None,
    ip_address: Optional[str] = None,
):
    try:
        log_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload_before=payload_before,
            payload_after=payload_after,
            ip_address=ip_address,
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        # Logging failure should not abort the transaction
        print(f"Failed to record audit log: {e}")

