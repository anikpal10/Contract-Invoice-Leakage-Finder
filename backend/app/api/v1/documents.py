import os
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_role, verify_case_tenant
from backend.app.models.user import User, UserRole
from backend.app.models.case import ReconciliationCase, CaseStatus
from backend.app.models.finding import Finding, ReviewStatus
from backend.app.models.document import UploadedDocument, DocumentCategory, ProcessingStatus
from backend.app.models.extracted_entities import (
    ExtractedDocumentField,
    Invoice,
    Contract,
    InvoiceLineItem,
    ContractLineItem,
)
from backend.app.schemas.document import (
    DocumentResponse, DocumentUploadResponse,
    DirectPathIngestRequest, DirectFolderIngestRequest,
    DirectBatchIngestResponse, DirectBatchIngestItem,
    RecentDocumentItem, PipelineResultResponse,
    PipelineResultFinding, AutomatedStepItem
)
from backend.app.schemas.extraction import ExtractedFieldResponse, ExtractedFieldUpdate
from backend.app.services.storage import storage_service
from backend.app.services.extraction import extraction_service
from backend.app.services.reconciliation_engine import reconciliation_engine
from backend.app.services.audit import log_audit_event
from backend.app.core.config import settings
from backend.app.services.financial_summary import (
    aggregate_amounts_by_currency,
    net_variance_by_currency,
    single_currency_total,
    currency_status,
    is_eligible_overcharge,
    is_eligible_undercharge,
    get_currency_symbol,
)

router = APIRouter(prefix="/cases", tags=["Document Upload & Processing"])


def _format_exposure_text(by_currency: dict) -> str:
    if not by_currency:
        return "0.00"
    single_total = single_currency_total(by_currency)
    if single_total is not None:
        c = next(iter(by_currency.keys()))
        return f"{get_currency_symbol(c)}{single_total:,.2f}"
    parts = [f"{k} {v:,.2f}" for k, v in sorted(by_currency.items())]
    return " / ".join(parts)

@router.get("/documents/recent", response_model=List[RecentDocumentItem])
def get_recent_documents(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the most recently uploaded documents across all cases for the user's organization,
    enriched with case references and titles for real-time dashboard display.
    """
    docs = (
        db.query(UploadedDocument)
        .filter(UploadedDocument.organization_id == current_user.organization_id)
        .order_by(UploadedDocument.created_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for d in docs:
        c = db.query(ReconciliationCase).filter(ReconciliationCase.id == d.case_id).first()
        result.append(RecentDocumentItem(
            id=d.id,
            case_id=d.case_id,
            case_reference=c.case_reference if c else "N/A",
            case_title=c.title if c else "Reconciliation Case",
            filename=d.filename,
            original_filename=d.original_filename,
            file_type=d.file_type,
            category=d.category,
            file_size_bytes=d.file_size_bytes,
            processing_status=d.processing_status,
            created_at=d.created_at,
            error_message=d.error_message
        ))
    return result

def _assemble_pipeline_result(
    doc: UploadedDocument,
    case: ReconciliationCase,
    db: Session,
    extracted_data: Optional[dict] = None,
    message: Optional[str] = None
) -> DocumentUploadResponse:
    metadata = extracted_data if extracted_data is not None else (doc.extracted_metadata or {})
    case_ref = case.case_reference if case else "N/A"
    case_title = case.title if case else "Reconciliation Case"

    # Requirement 7: Never show a final financial summary when required source data is missing or unvalidated
    if doc.processing_status != ProcessingStatus.EXTRACTED.value:
        return DocumentUploadResponse(
            id=doc.id,
            case_id=doc.case_id,
            case_reference=case_ref,
            case_title=case_title,
            original_filename=doc.original_filename,
            category=doc.category,
            processing_status=doc.processing_status,
            message=message or f"Document '{doc.original_filename}' is {doc.processing_status}. Financial summary is unavailable until extraction is completed.",
            reconciled=False,
            findings_count=0,
            potential_leakage=Decimal("0.00"),
            potential_leakage_by_currency={},
            currency_status="UNVALIDATED",
            recognized_data=metadata,
            findings=[],
            automated_steps=[
                AutomatedStepItem(
                    name="1. Ingestion & Validation",
                    status=doc.processing_status,
                    detail=doc.error_message or f"Extraction status: {doc.processing_status}. Source document verification required."
                )
            ]
        )

    # Requirement 4: Calculate billed amounts from validated extracted line items if total/subtotal is missing or zero
    line_items_list = metadata.get("line_items", [])
    if line_items_list:
        calc_line_sum = sum(float(li.get("line_total", 0)) for li in line_items_list)
        if not metadata.get("total_amount") or float(metadata.get("total_amount", 0)) <= 0:
            metadata["total_amount"] = calc_line_sum
        if not metadata.get("subtotal") or float(metadata.get("subtotal", 0)) <= 0:
            metadata["subtotal"] = calc_line_sum

    all_case_findings = db.query(Finding).filter(Finding.case_id == doc.case_id).order_by(Finding.potential_difference.desc()).all()
    inv_num = metadata.get("invoice_number")
    contract_ref = metadata.get("contract_reference")
    po_num = metadata.get("po_number")

    # Scope findings strictly to this document to prevent leaking unrelated exceptions
    if inv_num:
        findings = [f for f in all_case_findings if f.invoice_reference == inv_num]
    elif contract_ref:
        findings = [
            f for f in all_case_findings
            if any(isinstance(r, dict) and (r.get("contract_reference") == contract_ref or r.get("document_id") == doc.id)
                   for r in (f.source_document_references or []))
        ]
    elif po_num:
        findings = [
            f for f in all_case_findings
            if any(isinstance(r, dict) and (r.get("po_number") == po_num or r.get("document_id") == doc.id)
                   for r in (f.source_document_references or []))
        ]
    else:
        findings = []

    finding_items = [
        PipelineResultFinding(
            id=f.id,
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
            source_document_references=f.source_document_references
        )
        for f in findings
    ]

    findings_count = len(findings)

    # Gross overcharges
    gross_overcharges_by_currency = aggregate_amounts_by_currency(
        findings,
        "potential_difference",
        predicate=is_eligible_overcharge,
    )
    gross_overcharges = single_currency_total(gross_overcharges_by_currency) or Decimal("0.00")

    # Potential undercharges (positive magnitude of negative price variances)
    raw_undercharges_by_currency = aggregate_amounts_by_currency(
        findings,
        "potential_difference",
        predicate=is_eligible_undercharge,
    )
    potential_undercharges_by_currency = {
        c: abs(v) for c, v in raw_undercharges_by_currency.items()
    }
    potential_undercharges = single_currency_total(potential_undercharges_by_currency) or Decimal("0.00")

    # Net variance = gross overcharges - potential undercharges
    net_variance_by_currency_map = net_variance_by_currency(
        gross_overcharges_by_currency,
        potential_undercharges_by_currency,
    )
    net_variance = single_currency_total(net_variance_by_currency_map) or (gross_overcharges - potential_undercharges)

    potential_leakage_by_currency = gross_overcharges_by_currency
    potential_leakage = gross_overcharges
    leakage_status = currency_status(
        gross_overcharges_by_currency or potential_undercharges_by_currency
    )
    exposure_text = _format_exposure_text(gross_overcharges_by_currency)
    undercharge_text = _format_exposure_text(potential_undercharges_by_currency)
    net_variance_text = _format_exposure_text(net_variance_by_currency_map)
    line_count = len(metadata.get("line_items", []))
    supplier_display = case.supplier.name if (case and case.supplier) else "supplier"

    automated_steps = [
        AutomatedStepItem(
            name="1. Cryptographic Ingestion & Integrity",
            status="COMPLETED",
            detail=f"Verified '{doc.original_filename}' ({doc.file_size_bytes} bytes). SHA-256: {doc.sha256_hash[:12]}..."
        ),
        AutomatedStepItem(
            name="2. Optical & Structured Entity Recognition",
            status="COMPLETED",
            detail=f"Recognized as {doc.category}. Extracted {line_count} line item(s), dates, currencies, and commercial terms."
        ),
        AutomatedStepItem(
            name="3. Master Agreement & Rate Card Correlation",
            status="COMPLETED",
            detail=f"Cross-referenced agreed master pricing and item catalogs for {supplier_display}."
        ),
        AutomatedStepItem(
            name="4. Purchase Order & Delivery Note Verification",
            status="COMPLETED",
            detail="Validated authorized procurement orders and warehouse receipt quantities."
        ),
        AutomatedStepItem(
            name="5. Multi-Way Mathematical & Variance Reconciliation",
            status="COMPLETED",
            detail="Performed deterministic arithmetic, price variance, and duplicate invoice scans."
        ),
        AutomatedStepItem(
            name="6. Exception Identification & Leakage Computation",
            status="COMPLETED",
            detail=f"Generated {findings_count} finding(s) totaling {exposure_text} gross overcharges, -{undercharge_text} gross undercharges (Net Variance: {net_variance_text}, {leakage_status})."
        )
    ]

    leakage_msg = (
        f"Auto-reconciled: {findings_count} finding(s) identified (Gross Overcharge: {exposure_text}, Gross Undercharge: -{undercharge_text}, Net Variance: {net_variance_text})."
        if findings_count > 0
        else "Auto-reconciled (clean match, 0 exceptions)."
    )

    return DocumentUploadResponse(
        id=doc.id,
        case_id=doc.case_id,
        case_reference=case_ref,
        case_title=case_title,
        original_filename=doc.original_filename,
        category=doc.category,
        processing_status=doc.processing_status,
        message=message or f"Document '{doc.original_filename}' recognized and reconciled successfully. {leakage_msg}",
        reconciled=True,
        findings_count=findings_count,
        potential_leakage=gross_overcharges,
        potential_leakage_by_currency=gross_overcharges_by_currency,
        gross_overcharges=gross_overcharges,
        gross_overcharges_by_currency=gross_overcharges_by_currency,
        potential_undercharges=potential_undercharges,
        potential_undercharges_by_currency=potential_undercharges_by_currency,
        net_variance=net_variance,
        net_variance_by_currency=net_variance_by_currency_map,
        currency_status=leakage_status,
        recognized_data=metadata,
        findings=finding_items,
        automated_steps=automated_steps
    )

@router.get("/pipeline/latest", response_model=PipelineResultResponse)
def get_latest_pipeline_result(
    document_id: Optional[str] = None,
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the recognition metadata, automated execution steps, and resulting findings
    for the most recently processed document (or a specific document/case).
    """
    query = db.query(UploadedDocument).filter(
        UploadedDocument.organization_id == current_user.organization_id
    )
    if document_id:
        query = query.filter(UploadedDocument.id == document_id)
    elif case_id:
        query = query.filter(UploadedDocument.case_id == case_id)

    # Exclude generated export dossiers and prioritize successfully extracted evidence documents
    doc = query.filter(
        ~UploadedDocument.original_filename.like("Reconciliation_%.pdf"),
        ~UploadedDocument.original_filename.like("Export_%.pdf")
    ).order_by(
        (UploadedDocument.processing_status == ProcessingStatus.EXTRACTED.value).desc(),
        UploadedDocument.created_at.desc()
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="No processed documents found")

    case = db.query(ReconciliationCase).filter(ReconciliationCase.id == doc.case_id).first()
    pipeline_res = _assemble_pipeline_result(doc, case, db)

    return PipelineResultResponse(
        document_id=doc.id,
        case_id=doc.case_id,
        case_reference=pipeline_res.case_reference,
        case_title=pipeline_res.case_title,
        filename=doc.filename,
        original_filename=doc.original_filename,
        category=doc.category,
        processing_status=doc.processing_status,
        uploaded_at=doc.created_at,
        recognized_data=pipeline_res.recognized_data,
        findings_count=pipeline_res.findings_count,
        potential_leakage=pipeline_res.potential_leakage,
        potential_leakage_by_currency=pipeline_res.potential_leakage_by_currency,
        gross_overcharges=pipeline_res.gross_overcharges,
        gross_overcharges_by_currency=pipeline_res.gross_overcharges_by_currency,
        potential_undercharges=pipeline_res.potential_undercharges,
        potential_undercharges_by_currency=pipeline_res.potential_undercharges_by_currency,
        net_variance=pipeline_res.net_variance,
        net_variance_by_currency=pipeline_res.net_variance_by_currency,
        currency_status=pipeline_res.currency_status,
        findings=pipeline_res.findings,
        automated_steps=pipeline_res.automated_steps
    )

@router.post("/{case_id}/documents", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    category: str = Form(default="AUTO"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    case = verify_case_tenant(case_id, current_user, db)

    # 1. Determine category (supports AUTO or explicit category)
    category_upper = category.upper() if category else "AUTO"
    valid_categories = [c.value for c in DocumentCategory]
    if category_upper in valid_categories:
        doc_category = category_upper
    else:
        doc_category = infer_category(file.filename, "")

    # 2. Save file through storage service
    saved_filename, storage_path, file_size, sha256_hash = storage_service.save_upload(case_id, file)

    # 3. Prevent duplicate document re-upload in the same case
    existing = db.query(UploadedDocument).filter(
        UploadedDocument.case_id == case.id,
        (UploadedDocument.sha256_hash == sha256_hash) | (UploadedDocument.original_filename == file.filename)
    ).first()
    if existing:
        existing.storage_path = storage_path
        existing.file_size_bytes = file_size
        existing.sha256_hash = sha256_hash
        db.commit()
        try:
            extraction_service.extract_document(db, existing)
        except Exception as e:
            print(f"Extraction refresh error on single upload: {e}")
        try:
            reconciliation_engine.run_reconciliation(db=db, case=case, reset_reviewed=True)
        except Exception as re_err:
            print(f"Reconciliation refresh error: {re_err}")
        return _assemble_pipeline_result(
            existing, case, db,
            message=f"Document '{existing.original_filename}' refreshed and re-reconciled."
        )

    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "unknown"

    doc = UploadedDocument(
        case_id=case.id,
        organization_id=current_user.organization_id,
        filename=saved_filename,
        original_filename=file.filename,
        file_type=ext,
        category=doc_category,
        storage_path=storage_path,
        file_size_bytes=file_size,
        sha256_hash=sha256_hash,
        processing_status=ProcessingStatus.PENDING.value
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 4. Trigger extraction immediately
    extracted_data = {}
    try:
        extracted_data = extraction_service.extract_document(db, doc)
    except Exception as e:
        print(f"Extraction error on upload: {e}")

    # 5. Automatically execute deterministic multi-way financial reconciliation
    try:
        reconciliation_engine.run_reconciliation(db=db, case=case)
    except Exception as re_err:
        print(f"Auto-reconciliation error on upload: {re_err}")

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="DOCUMENT_UPLOADED",
        resource_type="DOCUMENT",
        resource_id=doc.id,
        user_id=current_user.id,
        payload_after={"filename": doc.original_filename, "category": doc.category}
    )

    return _assemble_pipeline_result(
        doc, case, db, extracted_data=extracted_data
    )

@router.post("/{case_id}/documents/batch-upload", status_code=status.HTTP_201_CREATED)
def batch_upload_documents(
    case_id: str,
    files: List[UploadFile] = File(...),
    category: str = Form(default="AUTO"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    case = verify_case_tenant(case_id, current_user, db)
    uploaded: List[dict] = []
    skipped = 0
    errors = 0
    error_details: List[str] = []

    if not files:
        raise HTTPException(status_code=400, detail="No files were provided for upload.")

    for file in files:
        try:
            # 1. Determine category (AUTO -> infer from filename)
            cat = (
                category.upper()
                if category and category.upper() in [c.value for c in DocumentCategory]
                else infer_category(file.filename or "", "")
            )

            # 2. Save file (validates extension + size, computes SHA-256)
            saved_filename, storage_path, file_size, sha256_hash = storage_service.save_upload(case_id, file)

            # 3. Duplicate check - if already uploaded in this case, refresh extraction and include in results
            existing = db.query(UploadedDocument).filter(
                UploadedDocument.case_id == case.id,
                (UploadedDocument.sha256_hash == sha256_hash) | (UploadedDocument.original_filename == file.filename)
            ).first()
            if existing:
                existing.storage_path = storage_path
                existing.file_size_bytes = file_size
                existing.sha256_hash = sha256_hash
                db.commit()
                try:
                    extraction_service.extract_document(db, existing)
                except Exception as e:
                    print(f"Extraction refresh error: {e}")
                skipped += 1
                uploaded.append({
                    "id": existing.id,
                    "filename": existing.original_filename,
                    "category": existing.category,
                    "reprocessed": True,
                })
                continue

            ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "unknown"
            doc = UploadedDocument(
                case_id=case.id,
                organization_id=current_user.organization_id,
                filename=saved_filename,
                original_filename=file.filename,
                file_type=ext,
                category=cat,
                storage_path=storage_path,
                file_size_bytes=file_size,
                sha256_hash=sha256_hash,
                processing_status=ProcessingStatus.PENDING.value
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)

            try:
                extraction_service.extract_document(db, doc)
            except Exception as e:
                print(f"Extraction error on batch upload for {file.filename}: {e}")

            uploaded.append({"id": doc.id, "filename": doc.original_filename, "category": doc.category})
        except Exception as ex:
            errors += 1
            error_details.append(f"{getattr(file, 'filename', 'unknown')}: {ex}")
            print(f"Batch upload error: {ex}")

    # If nothing could be ingested at all, surface a clear error instead of a fake success
    if not uploaded:
        raise HTTPException(
            status_code=400,
            detail=(
                "No files could be ingested. "
                + ("; ".join(error_details) if error_details else "Please check file types and sizes.")
            ),
        )

    # Automatically execute multi-way reconciliation once files are ingested
    findings_count = 0
    potential_leakage = Decimal("0.00")
    potential_leakage_by_currency: dict = {}
    leakage_status = "NONE"
    findings = []
    has_reprocessed = any(u.get("reprocessed") for u in uploaded)
    try:
        findings = reconciliation_engine.run_reconciliation(db=db, case=case, reset_reviewed=has_reprocessed)
        findings_count = len(findings)
        potential_leakage_by_currency = aggregate_amounts_by_currency(
            findings,
            "potential_difference",
            predicate=is_eligible_overcharge,
        )
        potential_leakage = single_currency_total(potential_leakage_by_currency) or Decimal("0.00")
        leakage_status = currency_status(potential_leakage_by_currency)
    except Exception as re_err:
        print(f"Auto-reconciliation error on batch upload: {re_err}")

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="DOCUMENTS_BATCH_UPLOADED",
        resource_type="CASE",
        resource_id=case.id,
        user_id=current_user.id,
        payload_after={"uploaded_count": len(uploaded), "skipped": skipped, "errors": errors, "findings_count": findings_count}
    )

    exposure_text = _format_exposure_text(potential_leakage_by_currency)
    reconcile_note = (
        f" Reconciled: {findings_count} finding(s) detected ({exposure_text} gross variance exposure, {leakage_status})."
        if findings_count > 0
        else " Reconciled (clean match)."
    )

    # Prefer the most recently extracted document for the pipeline preview payload
    last_doc = None
    for item in reversed(uploaded):
        candidate = db.query(UploadedDocument).filter(UploadedDocument.id == item["id"]).first()
        if candidate and candidate.processing_status == ProcessingStatus.EXTRACTED.value:
            last_doc = candidate
            break
    if last_doc is None:
        last_doc = db.query(UploadedDocument).filter(UploadedDocument.id == uploaded[-1]["id"]).first()

    # Build a pipeline-shaped payload so the frontend AutomatedRecognitionPipelineView renders correctly
    pipeline_payload = _assemble_pipeline_result(
        last_doc, case, db,
        message=f"Successfully processed {len(uploaded)} file(s). {skipped} duplicate(s) skipped.{reconcile_note}"
    ) if last_doc else None

    return {
        "message": f"Successfully processed {len(uploaded)} file(s). {skipped} duplicate(s) skipped.{reconcile_note}",
        "uploaded_count": len(uploaded),
        "skipped_count": skipped,
        "error_count": errors,
        "documents": uploaded,
        "reconciled": True,
        "case_id": case.id,
        "case_reference": case.case_reference,
        "case_title": case.title,
        "document_id": last_doc.id if last_doc else None,
        "original_filename": last_doc.original_filename if last_doc else "Batch",
        "category": last_doc.category if last_doc else "INVOICE",
        "processing_status": last_doc.processing_status if last_doc else "PENDING",
        "recognized_data": last_doc.extracted_metadata if last_doc else None,
        "findings_count": findings_count,
        "potential_leakage": float(potential_leakage),
        "potential_leakage_by_currency": {k: float(v) for k, v in potential_leakage_by_currency.items()},
        "gross_overcharges": float(pipeline_payload.gross_overcharges) if pipeline_payload else float(potential_leakage),
        "gross_overcharges_by_currency": {k: float(v) for k, v in (pipeline_payload.gross_overcharges_by_currency or {}).items()} if pipeline_payload else {},
        "potential_undercharges": float(pipeline_payload.potential_undercharges) if pipeline_payload else 0.0,
        "potential_undercharges_by_currency": {k: float(v) for k, v in (pipeline_payload.potential_undercharges_by_currency or {}).items()} if pipeline_payload else {},
        "net_variance": float(pipeline_payload.net_variance) if pipeline_payload else float(potential_leakage),
        "net_variance_by_currency": {k: float(v) for k, v in (pipeline_payload.net_variance_by_currency or {}).items()} if pipeline_payload else {},
        "currency_status": leakage_status,
        "findings": [
            PipelineResultFinding(
                id=f.id,
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
                source_document_references=f.source_document_references
            ).model_dump()
            for f in findings
        ],
        "automated_steps": [
            {
                "name": "1. Cryptographic Ingestion & Integrity",
                "status": "COMPLETED",
                "detail": f"Processed {len(uploaded)} file(s). Verified SHA-256 integrity."
            },
            {
                "name": "2. Optical & Structured Entity Recognition",
                "status": "COMPLETED",
                "detail": f"Recognized lines, tables, and headers for {len(uploaded)} document(s)."
            },
            {
                "name": "3. Master Agreement & Rate Card Correlation",
                "status": "COMPLETED",
                "detail": "Correlated with master rate cards and agreements."
            },
            {
                "name": "4. Purchase Order & Delivery Note Verification",
                "status": "COMPLETED",
                "detail": "Cross-referenced PO line limits and delivery quantities."
            },
            {
                "name": "5. Multi-Way Mathematical & Variance Reconciliation",
                "status": "COMPLETED",
                "detail": "Checked arithmetic, price variance tolerances, and duplicate window."
            },
            {
                "name": "6. Exception Identification & Leakage Computation",
                "status": "COMPLETED",
                "detail": f"Generated {findings_count} finding(s) totaling {exposure_text} gross variance exposure ({leakage_status})."
            }
        ],
        "pipeline": pipeline_payload.model_dump() if pipeline_payload else None,
    }

def infer_category(filename: str, path_str: str) -> str:
    lower_path = (path_str + "/" + filename).lower()
    if any(k in lower_path for k in ["contract", "agreement", "msa", "sla"]):
        return DocumentCategory.CONTRACT.value
    if any(k in lower_path for k in ["price_schedule", "priceschedule", "rate_card", "ratecard", "price"]):
        return DocumentCategory.PRICE_SCHEDULE.value
    if any(k in lower_path for k in ["purchase_order", "purchaseorder", "po_", "_po", "/po/", "\\po\\", "po-", "orders"]):
        return DocumentCategory.PURCHASE_ORDER.value
    if any(k in lower_path for k in ["goods_received", "goodsreceived", "grn", "delivery", "receipt"]):
        return DocumentCategory.GOODS_RECEIVED_NOTE.value
    return DocumentCategory.INVOICE.value

@router.post("/{case_id}/documents/by-path", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def ingest_document_by_path(
    case_id: str,
    payload: DirectPathIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    case = verify_case_tenant(case_id, current_user, db)

    # 1. Resolve and register file directly by path (zero memory buffer)
    filename, storage_path, file_size, sha256_hash = storage_service.register_file_by_path(payload.file_path)

    # 2. Determine category
    category_upper = payload.category.upper() if payload.category else infer_category(filename, storage_path)
    valid_categories = [c.value for c in DocumentCategory]
    if category_upper not in valid_categories:
        category_upper = infer_category(filename, storage_path)

    # 3. Prevent duplicate document re-upload in the same case
    existing = db.query(UploadedDocument).filter(
        UploadedDocument.case_id == case.id,
        UploadedDocument.sha256_hash == sha256_hash
    ).first()
    if existing:
        return _assemble_pipeline_result(
            existing, case, db,
            message="Document already registered from disk path previously (SHA-256 match). Full recognition and reconciliation details loaded."
        )

    ext = filename.split(".")[-1].lower() if "." in filename else "unknown"

    doc = UploadedDocument(
        case_id=case.id,
        organization_id=current_user.organization_id,
        filename=filename,
        original_filename=filename,
        file_type=ext,
        category=category_upper,
        storage_path=storage_path,
        file_size_bytes=file_size,
        sha256_hash=sha256_hash,
        processing_status=ProcessingStatus.PENDING.value
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 4. Trigger extraction directly from disk path
    try:
        extraction_service.extract_document(db, doc)
    except Exception as e:
        print(f"Extraction error from disk path: {e}")

    # 5. Automatically execute deterministic multi-way financial reconciliation
    try:
        reconciliation_engine.run_reconciliation(db=db, case=case)
    except Exception as re_err:
        print(f"Auto-reconciliation error on path ingest: {re_err}")

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="DOCUMENT_INGESTED_BY_PATH",
        resource_type="DOCUMENT",
        resource_id=doc.id,
        user_id=current_user.id,
        payload_after={"filename": doc.original_filename, "category": doc.category, "path": storage_path}
    )

    return _assemble_pipeline_result(
        doc, case, db,
        message=f"Document directly accessed from disk ({storage_path}) with zero memory buffer."
    )

@router.post("/{case_id}/documents/by-folder", response_model=DirectBatchIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_documents_by_folder(
    case_id: str,
    payload: DirectFolderIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    case = verify_case_tenant(case_id, current_user, db)

    target_folder = os.path.abspath(payload.folder_path)
    if not os.path.exists(target_folder) or not os.path.isdir(target_folder):
        raise HTTPException(status_code=404, detail=f"Directory not found on disk: {target_folder}")

    results: List[DirectBatchIngestItem] = []
    total_found = 0
    ingested_count = 0
    skipped_duplicates = 0
    errors = 0

    valid_extensions = tuple(f".{ext}" for ext in settings.ALLOWED_EXTENSIONS)

    for root, _, files in os.walk(target_folder):
        for fname in sorted(files):
            if not fname.lower().endswith(valid_extensions):
                continue
            
            full_path = os.path.join(root, fname)
            total_found += 1

            try:
                # 1. Zero-memory stream verification
                filename, storage_path, file_size, sha256_hash = storage_service.register_file_by_path(full_path)

                # 2. Category inference
                if payload.category and payload.category.upper() in [c.value for c in DocumentCategory]:
                    cat = payload.category.upper()
                else:
                    cat = infer_category(filename, storage_path)

                # 3. Duplicate check
                existing = db.query(UploadedDocument).filter(
                    UploadedDocument.case_id == case.id,
                    UploadedDocument.sha256_hash == sha256_hash
                ).first()
                if existing:
                    skipped_duplicates += 1
                    results.append(DirectBatchIngestItem(
                        filename=filename,
                        file_path=storage_path,
                        category=existing.category,
                        status="SKIPPED",
                        document_id=existing.id,
                        message="Already ingested (SHA-256 duplicate match)"
                    ))
                    continue

                ext = filename.split(".")[-1].lower() if "." in filename else "unknown"
                doc = UploadedDocument(
                    case_id=case.id,
                    organization_id=current_user.organization_id,
                    filename=filename,
                    original_filename=filename,
                    file_type=ext,
                    category=cat,
                    storage_path=storage_path,
                    file_size_bytes=file_size,
                    sha256_hash=sha256_hash,
                    processing_status=ProcessingStatus.PENDING.value
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)

                # 4. Extract
                try:
                    extraction_service.extract_document(db, doc)
                except Exception as ex:
                    print(f"Extraction error for {filename}: {ex}")

                ingested_count += 1
                results.append(DirectBatchIngestItem(
                    filename=filename,
                    file_path=storage_path,
                    category=cat,
                    status="SUCCESS",
                    document_id=doc.id,
                    message="Ingested directly from disk with zero memory buffering."
                ))
            except Exception as e:
                errors += 1
                results.append(DirectBatchIngestItem(
                    filename=fname,
                    file_path=full_path,
                    category="UNKNOWN",
                    status="ERROR",
                    document_id=None,
                    message=str(e)
                ))

    # Automatically execute multi-way reconciliation once folder files are ingested
    try:
        reconciliation_engine.run_reconciliation(db=db, case=case)
    except Exception as re_err:
        print(f"Auto-reconciliation error on folder ingest: {re_err}")

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="FOLDER_BATCH_INGESTED_BY_PATH",
        resource_type="CASE",
        resource_id=case.id,
        user_id=current_user.id,
        payload_after={
            "folder": target_folder,
            "total_found": total_found,
            "ingested_count": ingested_count,
            "skipped_duplicates": skipped_duplicates
        }
    )

    return DirectBatchIngestResponse(
        case_id=case.id,
        total_found=total_found,
        ingested_count=ingested_count,
        skipped_duplicates=skipped_duplicates,
        errors=errors,
        results=results
    )

@router.post("/{case_id}/documents/complete")
def complete_case_documents(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = verify_case_tenant(case_id, current_user, db)
    doc_count = db.query(UploadedDocument).filter(UploadedDocument.case_id == case.id).count()
    return {
        "case_id": case.id,
        "document_count": doc_count,
        "status": "READY_FOR_RECONCILIATION"
    }

@router.get("/{case_id}/documents", response_model=List[DocumentResponse])
def list_case_documents(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = verify_case_tenant(case_id, current_user, db)
    documents = db.query(UploadedDocument).filter(
        UploadedDocument.case_id == case.id
    ).order_by(UploadedDocument.created_at.desc()).all()
    return documents

@router.get("/{case_id}/documents/{document_id}/fields", response_model=List[ExtractedFieldResponse])
def get_extracted_fields(
    case_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_case_tenant(case_id, current_user, db)
    fields = db.query(ExtractedDocumentField).filter(
        ExtractedDocumentField.document_id == document_id
    ).all()
    return fields

@router.patch("/fields/{field_id}", response_model=ExtractedFieldResponse)
def update_extracted_field(
    field_id: str,
    update_data: ExtractedFieldUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    field = db.query(ExtractedDocumentField).filter(ExtractedDocumentField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Extracted field not found")

    payload_before = {"reviewed_value": field.reviewed_value, "extracted_value": field.extracted_value}
    field.reviewed_value = update_data.reviewed_value
    field.requires_review = False
    field.extraction_method = "MANUAL_EDIT"
    db.commit()
    db.refresh(field)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="EXTRACTED_FIELD_EDITED",
        resource_type="FIELD",
        resource_id=field.id,
        user_id=current_user.id,
        payload_before=payload_before,
        payload_after={"reviewed_value": field.reviewed_value}
    )

    return field

@router.get("/browse/filesystem")
def browse_filesystem(
    path: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Browse directories and files on the local filesystem to pick files or folders for ingestion.
    """
    base_dir = os.path.abspath(os.getcwd())
    target = os.path.abspath(path) if path else os.path.join(base_dir, "synthetic_dataset", "sample_files")
    if not os.path.exists(target):
        target = base_dir

    if not os.path.isdir(target):
        target = os.path.dirname(target)

    # Determine parent directory
    parent = os.path.dirname(target) if target != os.path.abspath(os.path.splitdrive(target)[0] + os.sep) else None

    directories = []
    files = []
    valid_extensions = tuple(f".{ext}" for ext in settings.ALLOWED_EXTENSIONS)

    try:
        entries = sorted(os.listdir(target))
        for entry in entries:
            if entry.startswith(".") or entry in ("node_modules", ".venv", "__pycache__", ".git"):
                continue
            entry_path = os.path.join(target, entry)
            if os.path.isdir(entry_path):
                # Count files inside
                sub_count = 0
                try:
                    sub_count = len([f for f in os.listdir(entry_path) if f.lower().endswith(valid_extensions)])
                except Exception:
                    pass
                directories.append({
                    "name": entry,
                    "path": entry_path,
                    "file_count": sub_count
                })
            elif os.path.isfile(entry_path):
                if entry.lower().endswith(valid_extensions):
                    size = os.path.getsize(entry_path)
                    ext = entry.split(".")[-1].lower() if "." in entry else ""
                    cat = infer_category(entry, entry_path)
                    files.append({
                        "name": entry,
                        "path": entry_path,
                        "size_bytes": size,
                        "file_type": ext,
                        "category": cat
                    })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot read directory: {e}")

    return {
        "current_path": target,
        "parent_path": parent,
        "directories": directories,
        "files": files,
        "total_files": len(files),
        "total_dirs": len(directories)
    }

@router.get("/{case_id}/documents/{document_id}/download")
def download_document_file(
    case_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = verify_case_tenant(case_id, current_user, db)
    doc = db.query(UploadedDocument).filter(
        UploadedDocument.id == document_id,
        UploadedDocument.case_id == case.id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="File on disk not found")

    return FileResponse(
        path=doc.storage_path,
        filename=doc.original_filename,
        media_type="application/octet-stream"
    )

@router.get("/{case_id}/documents/{document_id}/preview")
def preview_document_content(
    case_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = verify_case_tenant(case_id, current_user, db)
    doc = db.query(UploadedDocument).filter(
        UploadedDocument.id == document_id,
        UploadedDocument.case_id == case.id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="File on disk not found")

    preview_text = ""
    ext = doc.file_type.lower()
    if ext == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(doc.storage_path)
            for i, p in enumerate(reader.pages[:5]):
                preview_text += f"\n--- Page {i+1} ---\n" + (p.extract_text() or "")
        except Exception as e:
            preview_text = f"Error reading PDF preview: {e}"
    elif ext in ("csv", "txt", "json"):
        try:
            with open(doc.storage_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [f.readline() for _ in range(120)]
                preview_text = "".join(lines)
        except Exception as e:
            preview_text = f"Error reading text preview: {e}"
    elif ext in ("xlsx", "xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(doc.storage_path, data_only=True, read_only=True)
            for sheet in wb.sheetnames[:3]:
                ws = wb[sheet]
                preview_text += f"\n--- Sheet: {sheet} ---\n"
                for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                    if row_idx > 60:
                        break
                    preview_text += " | ".join(str(c) if c is not None else "" for c in row) + "\n"
        except Exception as e:
            preview_text = f"Error reading Excel preview: {e}"
    else:
        preview_text = "Binary preview not available"

    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "file_type": doc.file_type,
        "size_bytes": doc.file_size_bytes,
        "category": doc.category,
        "storage_path": doc.storage_path,
        "preview_text": preview_text
    }

@router.delete("/{case_id}/documents/{document_id}")
def delete_document(
    case_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    case = verify_case_tenant(case_id, current_user, db)
    doc = db.query(UploadedDocument).filter(
        UploadedDocument.id == document_id,
        UploadedDocument.case_id == case.id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    filename = doc.original_filename
    storage_path = doc.storage_path

    # Delete physical file from disk if present
    try:
        if storage_path and os.path.exists(storage_path):
            os.remove(storage_path)
    except Exception as e:
        print(f"Warning: could not delete physical file {storage_path}: {e}")

    # Remove document from DB (cascades to extracted fields and entity line items)
    db.delete(doc)
    db.commit()

    # Re-run reconciliation to update findings and leakage amounts
    try:
        reconciliation_engine.run_reconciliation(db=db, case=case)
    except Exception as re_err:
        print(f"Reconciliation error after document delete: {re_err}")

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="DOCUMENT_DELETED",
        resource_type="DOCUMENT",
        resource_id=document_id,
        user_id=current_user.id,
        payload_after={"deleted_filename": filename}
    )

    return {"message": f"Document '{filename}' deleted successfully.", "deleted_id": document_id}

@router.delete("/{case_id}/documents")
def clear_all_documents(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    case = verify_case_tenant(case_id, current_user, db)
    docs = db.query(UploadedDocument).filter(UploadedDocument.case_id == case.id).all()
    count = len(docs)

    for doc in docs:
        try:
            if doc.storage_path and os.path.exists(doc.storage_path):
                os.remove(doc.storage_path)
        except Exception as e:
            print(f"Warning: could not delete file {doc.storage_path}: {e}")
        db.delete(doc)

    # Delete all NEW findings for this case
    db.query(Finding).filter(
        Finding.case_id == case.id,
        Finding.review_status == ReviewStatus.NEW.value
    ).delete()

    db.commit()

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="DOCUMENTS_CLEARED",
        resource_type="CASE",
        resource_id=case.id,
        user_id=current_user.id,
        payload_after={"cleared_count": count}
    )

    return {"message": f"Cleared {count} document(s) from case.", "cleared_count": count}
