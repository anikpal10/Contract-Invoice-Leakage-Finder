from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.models.rule_config import RuleConfiguration
from backend.app.schemas.rule_config import RuleConfigCreate, RuleConfigResponse
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/admin", tags=["Admin Rule Configuration"])

@router.get("/rule-config", response_model=RuleConfigResponse)
def get_active_rule_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    config = db.query(RuleConfiguration).filter(
        RuleConfiguration.organization_id == current_user.organization_id,
        RuleConfiguration.is_active == True
    ).order_by(RuleConfiguration.version.desc()).first()

    if not config:
        # Create baseline v1 config
        config = RuleConfiguration(
            organization_id=current_user.organization_id,
            version=1,
            is_active=True,
            price_variance_tolerance_pct=0.0,
            price_variance_tolerance_abs=0.0,
            quantity_variance_tolerance_pct=0.0,
            duplicate_window_days=90,
            fuzzy_match_threshold=85,
            high_severity_threshold=500.0,
            critical_severity_threshold=2500.0,
            require_grn_for_goods=True,
            created_by_id=current_user.id,
            change_reason="Default baseline initialization"
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    return config

@router.put("/rule-config", response_model=RuleConfigResponse)
def update_rule_config(
    request: RuleConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    # Fetch current active config
    current_config = db.query(RuleConfiguration).filter(
        RuleConfiguration.organization_id == current_user.organization_id,
        RuleConfiguration.is_active == True
    ).order_by(RuleConfiguration.version.desc()).first()

    new_version = (current_config.version + 1) if current_config else 1

    # Deactivate current config
    if current_config:
        current_config.is_active = False

    # Create new versioned config
    new_config = RuleConfiguration(
        organization_id=current_user.organization_id,
        version=new_version,
        is_active=True,
        price_variance_tolerance_pct=request.price_variance_tolerance_pct,
        price_variance_tolerance_abs=request.price_variance_tolerance_abs,
        quantity_variance_tolerance_pct=request.quantity_variance_tolerance_pct,
        duplicate_window_days=request.duplicate_window_days,
        fuzzy_match_threshold=request.fuzzy_match_threshold,
        high_severity_threshold=request.high_severity_threshold,
        critical_severity_threshold=request.critical_severity_threshold,
        require_grn_for_goods=request.require_grn_for_goods,
        created_by_id=current_user.id,
        change_reason=request.change_reason or f"Updated to version {new_version}"
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="RULE_CONFIG_VERSIONED",
        resource_type="RULE_CONFIG",
        resource_id=new_config.id,
        user_id=current_user.id,
        payload_before={"version": current_config.version if current_config else 0},
        payload_after={"version": new_version, "reason": new_config.change_reason}
    )

    return new_config

@router.get("/rule-config/history", response_model=List[RuleConfigResponse])
def get_rule_config_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    history = db.query(RuleConfiguration).filter(
        RuleConfiguration.organization_id == current_user.organization_id
    ).order_by(RuleConfiguration.version.desc()).all()
    return history

