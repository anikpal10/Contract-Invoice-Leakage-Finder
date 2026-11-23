from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any
import os
from decimal import Decimal

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_role, verify_case_tenant
from backend.app.models.user import User, UserRole
from backend.app.models.finding import Finding, ReviewStatus
from backend.app.models.audit_log import ExportRecord
from backend.app.models.document import UploadedDocument
from backend.app.models.extracted_entities import Invoice, Contract
from backend.app.schemas.export import ExportRequest, ExportRecordResponse
from backend.app.services.report_generator import report_generator
from backend.app.services.audit import log_audit_event
from backend.app.services.financial_summary import (
    aggregate_amounts_by_currency,
    currency_status,
    single_currency_total,
    is_eligible_overcharge,
)

router = APIRouter(prefix="/cases", tags=["Reports & Exports"])

@router.get("/{case_id}/exports", response_model=List[ExportRecordResponse])
def list_case_exports(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = verify_case_tenant(case_id, current_user, db)
    records = db.query(ExportRecord).filter(
        ExportRecord.case_id == case.id,
        ExportRecord.organization_id == current_user.organization_id
    ).order_by(ExportRecord.created_at.desc()).all()

    return [
        ExportRecordResponse(
            id=r.id,
            case_id=r.case_id,
            format=r.format,
            file_name=r.file_name,
            record_count=r.record_count,
            total_leakage_amount=r.total_leakage_amount,
            created_at=r.created_at,
            download_url=f"/v1/cases/{case.id}/exports/{r.id}/download"
        )
        for r in records
    ]

@router.get("/{case_id}/full-dossier")
def get_case_full_dossier(
    case_id: str,
    document_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns complete reconciliation dossier data for on-screen live viewing and reporting.
    """
    case = verify_case_tenant(case_id, current_user, db)
    findings = db.query(Finding).filter(Finding.case_id == case.id).order_by(Finding.potential_difference.desc()).all()
    documents = db.query(UploadedDocument).filter(UploadedDocument.case_id == case.id).order_by(UploadedDocument.created_at.desc()).all()
    invoices = db.query(Invoice).filter(Invoice.case_id == case.id).all()
    contracts = db.query(Contract).filter(Contract.case_id == case.id).all()

    target_doc = None
    if document_id:
        if document_id.lower() == "latest":
            target_doc = documents[0] if documents else None
        else:
            target_doc = next((d for d in documents if d.id == document_id), None)

    if target_doc:
        meta = target_doc.extracted_metadata or {}
        inv_num = meta.get("invoice_number")
        contract_ref = meta.get("contract_reference")
        po_num = meta.get("po_number")

        filtered_findings = []
        for f in findings:
            refs = f.source_document_references or []
            doc_ids = [r.get("document_id") for r in refs if isinstance(r, dict)]
            if target_doc.id in doc_ids or (inv_num and f.invoice_reference == inv_num):
                filtered_findings.append(f)
            elif contract_ref and any(isinstance(r, dict) and (r.get("contract_reference") == contract_ref or r.get("document_id") == target_doc.id) for r in refs):
                filtered_findings.append(f)
            elif po_num and any(isinstance(r, dict) and (r.get("po_number") == po_num or r.get("document_id") == target_doc.id) for r in refs):
                filtered_findings.append(f)
        findings = filtered_findings

        related_doc_ids = {target_doc.id}
        for f in findings:
            for r in (f.source_document_references or []):
                if isinstance(r, dict) and r.get("document_id"):
                    related_doc_ids.add(r.get("document_id"))
        documents = [d for d in documents if d.id in related_doc_ids]

        if inv_num:
            invoices = [inv for inv in invoices if inv.invoice_number == inv_num or inv.document_id == target_doc.id]
        elif target_doc.id:
            invoices = [inv for inv in invoices if inv.document_id in related_doc_ids]

        if contract_ref:
            contracts = [c for c in contracts if c.contract_reference == contract_ref or c.document_id == target_doc.id]
        elif target_doc.id:
            contracts = [c for c in contracts if c.document_id in related_doc_ids]

    total_by_currency = aggregate_amounts_by_currency(
        findings,
        "potential_difference",
        predicate=is_eligible_overcharge,
    )
    total_potential = single_currency_total(total_by_currency) or Decimal("0.00")
    confirmed_findings = [f for f in findings if f.review_status == ReviewStatus.CONFIRMED.value]
    confirmed_by_currency = aggregate_amounts_by_currency(
        findings,
        "potential_difference",
        status_attr="review_status",
        status_equals=ReviewStatus.CONFIRMED.value,
        predicate=is_eligible_overcharge,
    )
    confirmed_leakage = single_currency_total(confirmed_by_currency) or Decimal("0.00")
    pending_findings = [f for f in findings if f.review_status == ReviewStatus.NEW.value]
    pending_by_currency = aggregate_amounts_by_currency(
        findings,
        "potential_difference",
        status_attr="review_status",
        status_equals=ReviewStatus.NEW.value,
        predicate=is_eligible_overcharge,
    )
    pending_leakage = single_currency_total(pending_by_currency) or Decimal("0.00")
    rejected_findings = [f for f in findings if f.review_status == ReviewStatus.REJECTED.value]

    currency = next(iter(total_by_currency.keys()), case.currency or "REVIEW_REQUIRED")
    status_marker = currency_status(total_by_currency or pending_by_currency or confirmed_by_currency)

    # Format extracted line items
    all_lines = []
    for inv in invoices:
        for li in (inv.line_items or []):
            all_lines.append({
                "invoice_number": inv.invoice_number,
                "line_number": li.line_number,
                "item_code": li.item_code,
                "description": li.description,
                "quantity": float(li.quantity) if li.quantity is not None else 0,
                "unit_price": float(li.unit_price) if li.unit_price is not None else 0,
                "line_total": float(li.line_total) if li.line_total is not None else 0,
                "currency": inv.currency
            })

    return {
        "case": {
            "id": case.id,
            "case_reference": case.case_reference,
            "title": case.title,
            "supplier_name": case.supplier.name if case.supplier else None,
            "currency": currency,
            "status": case.status,
            "created_at": case.created_at.isoformat() if case.created_at else None
        },
        "stats": {
            "total_documents": len(documents),
            "total_findings": len(findings),
            "total_potential_leakage": float(total_potential),
            "confirmed_leakage": float(confirmed_leakage),
            "pending_leakage": float(pending_leakage),
            "total_potential_leakage_by_currency": {k: float(v) for k, v in total_by_currency.items()},
            "confirmed_leakage_by_currency": {k: float(v) for k, v in confirmed_by_currency.items()},
            "pending_leakage_by_currency": {k: float(v) for k, v in pending_by_currency.items()},
            "currency_status": status_marker,
            "confirmed_count": len(confirmed_findings),
            "pending_count": len(pending_findings),
            "rejected_count": len(rejected_findings),
            "currency": currency
        },
        "documents": [
            {
                "id": d.id,
                "original_filename": d.original_filename,
                "category": d.category,
                "file_type": d.file_type,
                "file_size_bytes": d.file_size_bytes,
                "sha256_hash": d.sha256_hash,
                "processing_status": d.processing_status,
                "created_at": d.created_at.isoformat() if d.created_at else None
            }
            for d in documents
        ],
        "findings": [
            {
                "id": f.id,
                "invoice_reference": f.invoice_reference,
                "line_number": f.line_number,
                "supplier_name": f.supplier_name,
                "finding_category": f.finding_category,
                "item_code": f.item_code,
                "item_description": f.item_description,
                "expected_amount": float(f.expected_amount),
                "invoiced_amount": float(f.invoiced_amount),
                "potential_difference": float(f.potential_difference),
                "currency": f.currency,
                "severity": f.severity,
                "review_status": f.review_status,
                "calculation_explanation": f.calculation_explanation,
                "created_at": f.created_at.isoformat() if f.created_at else None
            }
            for f in findings
        ],
        "line_items": all_lines
    }

@router.post("/{case_id}/exports", response_model=ExportRecordResponse, status_code=status.HTTP_201_CREATED)
def generate_export_report(
    case_id: str,
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER, UserRole.VIEWER]))
):
    case = verify_case_tenant(case_id, current_user, db)
    org = case.organization

    query = db.query(Finding).filter(Finding.case_id == case.id)
    if not request.include_rejected:
        query = query.filter(Finding.review_status != ReviewStatus.REJECTED.value)
    findings = query.all()

    documents = db.query(UploadedDocument).filter(UploadedDocument.case_id == case.id).all()
    invoices = db.query(Invoice).filter(Invoice.case_id == case.id).all()
    contracts = db.query(Contract).filter(Contract.case_id == case.id).all()

    target_doc = None
    if request.document_id:
        if request.document_id.lower() == "latest":
            target_doc = db.query(UploadedDocument).filter(
                UploadedDocument.case_id == case.id
            ).order_by(UploadedDocument.created_at.desc()).first()
        else:
            target_doc = db.query(UploadedDocument).filter(
                UploadedDocument.id == request.document_id,
                UploadedDocument.case_id == case.id
            ).first()

    if target_doc:
        meta = target_doc.extracted_metadata or {}
        inv_num = meta.get("invoice_number")
        contract_ref = meta.get("contract_reference")
        po_num = meta.get("po_number")

        filtered_findings = []
        for f in findings:
            refs = f.source_document_references or []
            doc_ids = [r.get("document_id") for r in refs if isinstance(r, dict)]
            if target_doc.id in doc_ids or (inv_num and f.invoice_reference == inv_num):
                filtered_findings.append(f)
            elif contract_ref and any(isinstance(r, dict) and (r.get("contract_reference") == contract_ref or r.get("document_id") == target_doc.id) for r in refs):
                filtered_findings.append(f)
            elif po_num and any(isinstance(r, dict) and (r.get("po_number") == po_num or r.get("document_id") == target_doc.id) for r in refs):
                filtered_findings.append(f)
        findings = filtered_findings

        related_doc_ids = {target_doc.id}
        for f in findings:
            for r in (f.source_document_references or []):
                if isinstance(r, dict) and r.get("document_id"):
                    related_doc_ids.add(r.get("document_id"))
        documents = [d for d in documents if d.id in related_doc_ids]

        if inv_num:
            invoices = [inv for inv in invoices if inv.invoice_number == inv_num or inv.document_id == target_doc.id]
        elif target_doc.id:
            invoices = [inv for inv in invoices if inv.document_id in related_doc_ids]

        if contract_ref:
            contracts = [c for c in contracts if c.contract_reference == contract_ref or c.document_id == target_doc.id]
        elif target_doc.id:
            contracts = [c for c in contracts if c.document_id in related_doc_ids]

    fmt = request.format.upper()
    if fmt == "CSV":
        filename, filepath, count, total = report_generator.generate_csv_report(case, org, findings, target_document=target_doc)
    elif fmt == "PDF":
        filename, filepath, count, total = report_generator.generate_pdf_report(
            case, org, findings, documents=documents, invoices=invoices, contracts=contracts, target_document=target_doc
        )
    elif fmt in ["EXCEL", "XLSX"]:
        filename, filepath, count, total = report_generator.generate_excel_report(
            case, org, findings, documents=documents, invoices=invoices, contracts=contracts, target_document=target_doc
        )
        fmt = "EXCEL"
    elif fmt == "JSON":
        filename, filepath, count, total = report_generator.generate_json_dossier(
            case, org, findings, documents=documents, invoices=invoices, contracts=contracts, target_document=target_doc
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Supported formats: 'PDF', 'EXCEL', 'CSV', 'JSON'")

    record = ExportRecord(
        case_id=case.id,
        organization_id=current_user.organization_id,
        generated_by_id=current_user.id,
        format=fmt,
        file_name=filename,
        storage_path=filepath,
        record_count=count,
        total_leakage_amount=total
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    log_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        action="REPORT_EXPORTED",
        resource_type="EXPORT",
        resource_id=record.id,
        user_id=current_user.id,
        payload_after={"format": fmt, "filename": filename, "records": count}
    )

    download_url = f"/v1/cases/{case.id}/exports/{record.id}/download"
    return ExportRecordResponse(
        id=record.id,
        case_id=record.case_id,
        format=record.format,
        file_name=record.file_name,
        record_count=record.record_count,
        total_leakage_amount=record.total_leakage_amount,
        created_at=record.created_at,
        download_url=download_url
    )

@router.get("/{case_id}/exports/{export_id}/download")
def download_export_file(
    case_id: str,
    export_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = verify_case_tenant(case_id, current_user, db)
    record = db.query(ExportRecord).filter(
        ExportRecord.id == export_id,
        ExportRecord.organization_id == current_user.organization_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Export record not found")

    if not record.storage_path or not os.path.exists(record.storage_path):
        # Dynamically regenerate the missing export file on the fly
        org = case.organization
        findings = db.query(Finding).filter(Finding.case_id == case.id).all()
        documents = db.query(UploadedDocument).filter(UploadedDocument.case_id == case.id).all()
        invoices = db.query(Invoice).filter(Invoice.case_id == case.id).all()
        contracts = db.query(Contract).filter(Contract.case_id == case.id).all()

        fmt = record.format.upper()
        if fmt == "CSV":
            filename, filepath, count, total = report_generator.generate_csv_report(case, org, findings)
        elif fmt == "PDF":
            filename, filepath, count, total = report_generator.generate_pdf_report(
                case, org, findings, documents=documents, invoices=invoices, contracts=contracts
            )
        elif fmt in ["EXCEL", "XLSX"]:
            filename, filepath, count, total = report_generator.generate_excel_report(
                case, org, findings, documents=documents, invoices=invoices, contracts=contracts
            )
        elif fmt == "JSON":
            filename, filepath, count, total = report_generator.generate_json_dossier(
                case, org, findings, documents=documents, invoices=invoices, contracts=contracts
            )
        else:
            raise HTTPException(status_code=404, detail="Export file not found and format unsupported")

        record.storage_path = filepath
        record.file_name = filename
        record.record_count = count
        record.total_leakage_amount = total
        db.commit()

    media_types = {
        "PDF": "application/pdf",
        "CSV": "text/csv",
        "EXCEL": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "JSON": "application/json",
    }
    media_type = media_types.get(record.format.upper(), "application/octet-stream")

    return FileResponse(
        path=record.storage_path,
        media_type=media_type,
        filename=record.file_name,
        headers={
            "Content-Disposition": f'attachment; filename="{record.file_name}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@router.delete("/{case_id}/exports/{export_id}")
def delete_export_record(
    case_id: str,
    export_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.REVIEWER]))
):
    verify_case_tenant(case_id, current_user, db)
    record = db.query(ExportRecord).filter(
        ExportRecord.id == export_id,
        ExportRecord.organization_id == current_user.organization_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Export record not found")

    filename = record.file_name
    try:
        if record.storage_path and os.path.exists(record.storage_path):
            os.remove(record.storage_path)
    except Exception as e:
        print(f"Warning: could not delete physical export file {record.storage_path}: {e}")

    db.delete(record)
    db.commit()
    return {"message": f"Export '{filename}' deleted.", "deleted_id": export_id}

@router.delete("/{case_id}/exports")
def clear_all_exports(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    verify_case_tenant(case_id, current_user, db)
    records = db.query(ExportRecord).filter(
        ExportRecord.case_id == case_id,
        ExportRecord.organization_id == current_user.organization_id
    ).all()
    count = len(records)
    for r in records:
        try:
            if r.storage_path and os.path.exists(r.storage_path):
                os.remove(r.storage_path)
        except Exception:
            pass
        db.delete(r)

    db.commit()
    return {"message": f"Cleared {count} export(s).", "cleared_count": count}
