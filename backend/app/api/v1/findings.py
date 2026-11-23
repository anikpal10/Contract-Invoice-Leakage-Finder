from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.models.finding import Finding, ReviewDecision, ReviewStatus
from backend.app.models.document import UploadedDocument
from backend.app.schemas.finding import FindingResponse, FindingPatchRequest, FindingReviewAction, ReviewDecisionResponse
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/findings", tags=["Findings Management & Human Review"])

@router.get("/", response_model=List[FindingResponse])
def list_findings(
    case_id: Optional[str] = None,
    document_id: Optional[str] = None,
    review_status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Finding).filter(Finding.organization_id == current_user.organization_id)
    if case_id:
        query = query.filter(Finding.case_id == case_id)
    if review_status and review_status.upper() != "ALL":
        query = query.filter(Finding.review_status == review_status.upper())
    if severity and severity.upper() != "ALL":
        query = query.filter(Finding.severity == severity.upper())

    findings = query.order_by(Finding.potential_difference.desc()).limit(limit).all()

    if document_id:
        target_doc = None
        if document_id.lower() == "latest":
            doc_query = db.query(UploadedDocument).filter(
                UploadedDocument.organization_id == current_user.organization_id
            )
            if case_id:
                doc_query = doc_query.filter(UploadedDocument.case_id == case_id)
            target_doc = doc_query.order_by(UploadedDocument.created_at.desc()).first()
        else:
            target_doc = db.query(UploadedDocument).filter(
                UploadedDocument.id == document_id,
                UploadedDocument.organization_id == current_user.organization_id
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

    return [_build_finding_response(f) for f in findings]

@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    finding = db.query(Finding).filter(
        Finding.id == finding_id,
        Finding.organization_id == current_user.organization_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return _build_finding_response(finding)

@router.patch("/{finding_id}", response_model=FindingResponse)
def update_finding_status(
    finding_id: str,
    request: FindingPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    finding = db.query(Finding).filter(
        Finding.id == finding_id,
        Finding.organization_id == current_user.organization_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    prev_status = finding.review_status
    new_status = request.review_status or prev_status

    if request.review_status:
        valid_statuses = [s.value for s in ReviewStatus]
        if request.review_status.upper() not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid review status. Must be one of {valid_statuses}")
        finding.review_status = request.review_status.upper()

    if request.adjusted_amount is not None:
        finding.potential_difference = request.adjusted_amount

    # Record ReviewDecision
    decision = ReviewDecision(
        finding_id=finding.id,
        reviewer_id=current_user.id,
        action=f"STATUS_CHANGE_TO_{new_status}",
        previous_status=prev_status,
        new_status=new_status,
        comment=request.comment,
        adjusted_amount=request.adjusted_amount
    )
    db.add(decision)
    db.commit()
    db.refresh(finding)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="FINDING_REVIEWED",
        resource_type="FINDING",
        resource_id=finding.id,
        user_id=current_user.id,
        payload_before={"status": prev_status},
        payload_after={"status": finding.review_status, "comment": request.comment}
    )

    return _build_finding_response(finding)

@router.post("/{finding_id}/decisions", response_model=FindingResponse)
def record_review_decision(
    finding_id: str,
    action: FindingReviewAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    finding = db.query(Finding).filter(
        Finding.id == finding_id,
        Finding.organization_id == current_user.organization_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    prev_status = finding.review_status
    act = action.action.upper()
    if act == "CONFIRM":
        new_status = ReviewStatus.CONFIRMED.value
    elif act == "REJECT":
        new_status = ReviewStatus.REJECTED.value
    elif act in ("RESET", "REOPEN"):
        new_status = ReviewStatus.NEW.value
        finding.requires_more_info_reason = None
    elif act == "REQUEST_INFO":
        new_status = ReviewStatus.NEEDS_MORE_INFO.value
        finding.requires_more_info_reason = action.comment
    else:
        new_status = prev_status

    finding.review_status = new_status
    if action.adjusted_amount is not None:
        finding.potential_difference = action.adjusted_amount

    decision = ReviewDecision(
        finding_id=finding.id,
        reviewer_id=current_user.id,
        action=act,
        previous_status=prev_status,
        new_status=new_status,
        comment=action.comment,
        adjusted_amount=action.adjusted_amount
    )
    db.add(decision)
    db.commit()
    db.refresh(finding)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action=f"FINDING_DECISION_{act}",
        resource_type="FINDING",
        resource_id=finding.id,
        user_id=current_user.id,
        payload_after={"action": act, "new_status": new_status, "comment": action.comment}
    )

    return _build_finding_response(finding)

def _build_finding_response(f: Finding) -> FindingResponse:
    decisions_list = []
    for d in f.decisions:
        reviewer_name = d.reviewer.full_name if d.reviewer else "Unknown Reviewer"
        decisions_list.append(ReviewDecisionResponse(
            id=d.id,
            reviewer_id=d.reviewer_id,
            reviewer_name=reviewer_name,
            action=d.action,
            previous_status=d.previous_status,
            new_status=d.new_status,
            comment=d.comment,
            adjusted_amount=d.adjusted_amount,
            created_at=d.created_at
        ))

    return FindingResponse(
        id=f.id,
        case_id=f.case_id,
        finding_category=f.finding_category,
        supplier_name=f.supplier_name,
        invoice_reference=f.invoice_reference,
        line_number=f.line_number,
        item_code=f.item_code,
        item_description=f.item_description,
        expected_amount=f.expected_amount,
        invoiced_amount=f.invoiced_amount,
        potential_difference=f.potential_difference,
        currency=f.currency,
        severity=f.severity,
        review_status=f.review_status,
        calculation_explanation=f.calculation_explanation,
        source_document_references=f.source_document_references,
        rule_version=f.rule_version,
        requires_more_info_reason=f.requires_more_info_reason,
        created_at=f.created_at,
        updated_at=f.updated_at,
        decisions=decisions_list
    )

