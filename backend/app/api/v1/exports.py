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

    total_potential = sum((f.potential_difference for f in findings), Decimal("0.00"))
    confirmed_findings = [f for f in findings if f.review_status == ReviewStatus.CONFIRMED.value]
    confirmed_leakage = sum((f.potential_difference for f in confirmed_findings), Decimal("0.00"))
    pending_findings = [f for f in findings if f.review_status == ReviewStatus.NEW.value]
    pending_leakage = sum((f.potential_difference for f in pending_findings), Decimal("0.00"))
    rejected_findings = [f for f in findings if f.review_status == ReviewStatus.REJECTED.value]

    currency = findings[0].currency if findings else (case.currency or "GBP")

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

    fmt = request.format.upper()
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
        fmt = "EXCEL"
    elif fmt == "JSON":
        filename, filepath, count, total = report_generator.generate_json_dossier(
            case, org, findings, documents=documents, invoices=invoices, contracts=contracts
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
    verify_case_tenant(case_id, current_user, db)
    record = db.query(ExportRecord).filter(
        ExportRecord.id == export_id,
        ExportRecord.organization_id == current_user.organization_id
    ).first()
    if not record or not os.path.exists(record.storage_path):
        raise HTTPException(status_code=404, detail="Export file not found")

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
        headers={"Content-Disposition": f'attachment; filename="{record.file_name}"'}
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

