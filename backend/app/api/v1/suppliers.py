from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.models.supplier import Supplier
from backend.app.schemas.supplier import SupplierCreate, SupplierResponse
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

@router.get("/", response_model=List[SupplierResponse])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    suppliers = db.query(Supplier).filter(
        Supplier.organization_id == current_user.organization_id
    ).order_by(Supplier.name).all()
    return suppliers

@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    request: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    canonical_name = request.name.strip().upper()
    existing = db.query(Supplier).filter(
        Supplier.organization_id == current_user.organization_id,
        Supplier.canonical_name == canonical_name
    ).first()
    if existing:
        return existing

    supplier = Supplier(
        organization_id=current_user.organization_id,
        name=request.name.strip(),
        canonical_name=canonical_name,
        supplier_code=request.supplier_code,
        tax_id=request.tax_id,
        payment_terms=request.payment_terms,
        contact_email=str(request.contact_email) if request.contact_email else None
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="SUPPLIER_CREATED",
        resource_type="SUPPLIER",
        resource_id=supplier.id,
        user_id=current_user.id,
        payload_after={"name": supplier.name, "canonical": supplier.canonical_name}
    )

    return supplier

