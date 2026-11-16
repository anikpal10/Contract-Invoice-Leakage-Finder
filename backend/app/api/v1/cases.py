from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
import uuid
from datetime import datetime

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_role, verify_case_tenant, verify_workspace_tenant
from backend.app.models.user import User, UserRole
from backend.app.models.case import ReconciliationCase, CaseStatus
from backend.app.models.finding import Finding, ReviewStatus
from backend.app.models.document import UploadedDocument
from backend.app.models.supplier import Supplier
from backend.app.schemas.case import CaseCreate, CaseResponse, CaseSummaryStats, CaseAnalyticsResponse
from backend.app.schemas.finding import FindingResponse
from backend.app.services.reconciliation_engine import reconciliation_engine
from backend.app.services.pandas_processor import pandas_processor
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/cases", tags=["Reconciliation Cases"])

@router.get("/summary/dashboard", response_model=CaseSummaryStats)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = current_user.organization_id

    total_invoices = db.query(UploadedDocument).filter(
        UploadedDocument.organization_id == org_id,
        UploadedDocument.category == "INVOICE"
    ).count()

    total_documents = db.query(UploadedDocument).filter(
        UploadedDocument.organization_id == org_id
    ).count()

    total_cases = db.query(ReconciliationCase).filter(
        ReconciliationCase.organization_id == org_id
    ).count()

    all_findings = db.query(Finding).filter(
        Finding.organization_id == org_id
    ).all()

    # Only sum NEW (pending) findings for "Potential Leakage" KPI card
    potential_leakage = sum(
        (f.potential_difference for f in all_findings if f.review_status == ReviewStatus.NEW.value),
        Decimal("0.00")
    )
    # Separately track confirmed leakage (reviewed & confirmed)
    confirmed_leakage_amount = sum(
        (f.potential_difference for f in all_findings if f.review_status == ReviewStatus.CONFIRMED.value),
        Decimal("0.00")
    )
    awaiting = sum(1 for f in all_findings if f.review_status == ReviewStatus.NEW.value)
    confirmed = sum(1 for f in all_findings if f.review_status == ReviewStatus.CONFIRMED.value)
    rejected = sum(1 for f in all_findings if f.review_status == ReviewStatus.REJECTED.value)

    return CaseSummaryStats(
        total_invoices=total_invoices,
        total_cases=total_cases,
        total_documents=total_documents,
        potential_leakage=potential_leakage,
        confirmed_leakage_amount=confirmed_leakage_amount,
        findings_awaiting_review=awaiting,
        confirmed_findings=confirmed,
        rejected_findings=rejected
    )

@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    request: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    verify_workspace_tenant(request.workspace_id, current_user, db)

    ref_code = f"CASE-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
    new_case = ReconciliationCase(
        organization_id=current_user.organization_id,
        workspace_id=request.workspace_id,
        supplier_id=request.supplier_id,
        title=request.title,
        case_reference=ref_code,
        currency=request.currency or "GBP",
        date_from=request.date_from,
        date_to=request.date_to,
        notes=request.notes,
        created_by_id=current_user.id,
        status=CaseStatus.DRAFT.value
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="CASE_CREATED",
        resource_type="RECONCILIATION_CASE",
        resource_id=new_case.id,
        user_id=current_user.id,
        payload_after={"reference": new_case.case_reference, "title": new_case.title}
    )

    return _build_case_response(new_case, db)

@router.get("/", response_model=List[CaseResponse])
def list_cases(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ReconciliationCase).filter(
        ReconciliationCase.organization_id == current_user.organization_id
    )
    if workspace_id:
        query = query.filter(ReconciliationCase.workspace_id == workspace_id)

    cases = query.order_by(ReconciliationCase.created_at.desc()).all()
    return [_build_case_response(c, db) for c in cases]

@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = verify_case_tenant(case_id, current_user, db)
    return _build_case_response(case, db)

@router.post("/{case_id}/run", response_model=List[FindingResponse])
def run_reconciliation(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    case = verify_case_tenant(case_id, current_user, db)

    # Execute deterministic multi-way financial reconciliation
    findings = reconciliation_engine.run_reconciliation(db=db, case=case)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="RECONCILIATION_RUN",
        resource_type="RECONCILIATION_CASE",
        resource_id=case.id,
        user_id=current_user.id,
        payload_after={"findings_count": len(findings)}
    )

    return findings

@router.get("/{case_id}/findings", response_model=List[FindingResponse])
def get_case_findings(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = verify_case_tenant(case_id, current_user, db)
    findings = db.query(Finding).filter(
        Finding.case_id == case.id
    ).order_by(Finding.potential_difference.desc()).all()
    return findings

@router.get("/{case_id}/analytics", response_model=CaseAnalyticsResponse)
def get_case_analytics(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Computes Pandas-powered financial comparison analytics across all
    case invoices and reconciliation findings.
    """
    case = verify_case_tenant(case_id, current_user, db)
    analytics = pandas_processor.compute_dashboard_analytics(
        invoices=case.invoices,
        findings=case.findings
    )
    return analytics

def _build_case_response(c: ReconciliationCase, db: Session) -> CaseResponse:
    doc_count = db.query(UploadedDocument).filter(UploadedDocument.case_id == c.id).count()
    findings = db.query(Finding).filter(Finding.case_id == c.id).all()
    
    potential_total = sum((f.potential_difference for f in findings), Decimal("0.00"))
    confirmed_total = sum((f.potential_difference for f in findings if f.review_status == ReviewStatus.CONFIRMED.value), Decimal("0.00"))

    supplier_name = c.supplier.name if c.supplier else None

    return CaseResponse(
        id=c.id,
        organization_id=c.organization_id,
        workspace_id=c.workspace_id,
        supplier_id=c.supplier_id,
        supplier_name=supplier_name,
        title=c.title,
        case_reference=c.case_reference,
        currency=c.currency,
        status=c.status,
        date_from=c.date_from,
        date_to=c.date_to,
        notes=c.notes,
        created_at=c.created_at,
        updated_at=c.updated_at,
        document_count=doc_count,
        finding_count=len(findings),
        potential_leakage_amount=potential_total,
        confirmed_leakage_amount=confirmed_total
    )

