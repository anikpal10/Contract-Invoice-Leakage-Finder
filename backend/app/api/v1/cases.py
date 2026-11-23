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
from backend.app.services.financial_summary import (
    aggregate_amounts_by_currency,
    single_currency_total,
    currency_status,
    is_eligible_overcharge,
    is_eligible_undercharge,
    undercharge_amount,
    net_variance_by_currency,
)

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

    # Gross potential overcharge by currency (NEW only)
    potential_leakage_by_currency = aggregate_amounts_by_currency(
        all_findings,
        "potential_difference",
        status_attr="review_status",
        status_equals=ReviewStatus.NEW.value,
        predicate=is_eligible_overcharge,
    )
    potential_leakage = single_currency_total(potential_leakage_by_currency) or Decimal("0.00")

    # Confirmed overcharge by currency
    confirmed_leakage_by_currency = aggregate_amounts_by_currency(
        all_findings,
        "potential_difference",
        status_attr="review_status",
        status_equals=ReviewStatus.CONFIRMED.value,
        predicate=is_eligible_overcharge,
    )
    confirmed_leakage_amount = single_currency_total(confirmed_leakage_by_currency) or Decimal("0.00")

    # Potential undercharges (NEW only) - reported as positive magnitude per currency
    potential_undercharges_by_currency = aggregate_amounts_by_currency(
        all_findings,
        "potential_difference",
        status_attr="review_status",
        status_equals=ReviewStatus.NEW.value,
        predicate=is_eligible_undercharge,
    )
    # Convert stored negative variances to positive undercharge magnitudes
    potential_undercharges_by_currency = {
        c: abs(v) for c, v in potential_undercharges_by_currency.items()
    }
    potential_undercharges = single_currency_total(potential_undercharges_by_currency) or Decimal("0.00")

    # Net variance = gross overcharges - potential undercharges (kept separate from gross)
    net_variance_by_currency_map = net_variance_by_currency(
        potential_leakage_by_currency,
        potential_undercharges_by_currency,
    )
    net_variance = single_currency_total(net_variance_by_currency_map) or Decimal("0.00")

    status_marker = currency_status(
        potential_leakage_by_currency
        or confirmed_leakage_by_currency
        or potential_undercharges_by_currency
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
        potential_leakage_by_currency=potential_leakage_by_currency,
        confirmed_leakage_by_currency=confirmed_leakage_by_currency,
        gross_overcharges=potential_leakage,
        gross_overcharges_by_currency=potential_leakage_by_currency,
        potential_undercharges=potential_undercharges,
        potential_undercharges_by_currency=potential_undercharges_by_currency,
        net_variance=net_variance,
        net_variance_by_currency=net_variance_by_currency_map,
        currency_status=status_marker,
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
        currency=(request.currency or "REVIEW_REQUIRED"),
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
    document_id: Optional[str] = None,
    review_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = verify_case_tenant(case_id, current_user, db)
    query = db.query(Finding).filter(
        Finding.case_id == case.id
    )
    if review_status and review_status.upper() != "ALL":
        query = query.filter(Finding.review_status == review_status.upper())

    findings = query.order_by(Finding.potential_difference.desc()).all()

    if document_id:
        target_doc = None
        if document_id.lower() == "latest":
            target_doc = db.query(UploadedDocument).filter(
                UploadedDocument.case_id == case.id
            ).order_by(UploadedDocument.created_at.desc()).first()
        else:
            target_doc = db.query(UploadedDocument).filter(
                UploadedDocument.id == document_id,
                UploadedDocument.case_id == case.id
            ).first()

        if target_doc:
            meta = target_doc.extracted_metadata or {}
            inv_num = meta.get("invoice_number")
            contract_ref = meta.get("contract_reference")
            po_num = meta.get("po_number")

            filtered = []
            for f in findings:
                refs = f.source_document_references or []
                doc_ids = [r.get("document_id") for r in refs if isinstance(r, dict)]
                if target_doc.id in doc_ids or (inv_num and f.invoice_reference == inv_num):
                    filtered.append(f)
                elif contract_ref and any(isinstance(r, dict) and (r.get("contract_reference") == contract_ref or r.get("document_id") == target_doc.id) for r in refs):
                    filtered.append(f)
                elif po_num and any(isinstance(r, dict) and (r.get("po_number") == po_num or r.get("document_id") == target_doc.id) for r in refs):
                    filtered.append(f)
            findings = filtered
        else:
            findings = []

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
    
    potential_by_currency = aggregate_amounts_by_currency(
        findings,
        "potential_difference",
        predicate=is_eligible_overcharge,
    )
    confirmed_by_currency = aggregate_amounts_by_currency(
        findings,
        "potential_difference",
        status_attr="review_status",
        status_equals=ReviewStatus.CONFIRMED.value,
        predicate=is_eligible_overcharge,
    )
    potential_total = single_currency_total(potential_by_currency) or Decimal("0.00")
    confirmed_total = single_currency_total(confirmed_by_currency) or Decimal("0.00")
    status_marker = currency_status(potential_by_currency or confirmed_by_currency)

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
        confirmed_leakage_amount=confirmed_total,
        potential_leakage_by_currency=potential_by_currency,
        confirmed_leakage_by_currency=confirmed_by_currency,
        currency_status=status_marker,
    )
