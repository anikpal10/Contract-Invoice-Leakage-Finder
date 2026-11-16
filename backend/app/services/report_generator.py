import os
import csv
import json
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple, Optional, Any
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from backend.app.core.config import settings
from backend.app.models.finding import Finding, ReviewStatus
from backend.app.models.case import ReconciliationCase
from backend.app.models.organization import Organization
from backend.app.models.document import UploadedDocument
from backend.app.models.extracted_entities import Invoice, Contract

def get_currency_symbol(currency_code: Optional[str]) -> str:
    mapping = {
        "INR": "₹",
        "GBP": "£",
        "USD": "$",
        "EUR": "€",
    }
    return mapping.get((currency_code or "").upper(), "£")

class ReportGenerator:
    def __init__(self):
        self.export_dir = os.path.abspath(settings.LOCAL_EXPORT_DIR)
        os.makedirs(self.export_dir, exist_ok=True)

    def generate_csv_report(
        self,
        case: ReconciliationCase,
        org: Organization,
        findings: List[Finding]
    ) -> Tuple[str, str, int, Decimal]:
        """
        Generates structured CSV report for reconciliation case findings.
        Returns: (filename, full_storage_path, record_count, total_leakage)
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"Reconciliation_{case.case_reference}_{timestamp}.csv"
        filepath = os.path.join(self.export_dir, filename)

        headers = [
            "Organization",
            "Case Reference",
            "Case Title",
            "Supplier",
            "Invoice Reference",
            "Line Number",
            "Item Code",
            "Description",
            "Finding Category",
            "Expected Amount",
            "Invoiced Amount",
            "Potential Difference",
            "Currency",
            "Severity",
            "Review Status",
            "Calculation Explanation",
            "Rule Version",
            "Created Date",
            "Last Updated Date"
        ]

        total_leakage = Decimal("0.00")
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for f_item in findings:
                total_leakage += f_item.potential_difference
                writer.writerow([
                    org.name,
                    case.case_reference,
                    case.title,
                    f_item.supplier_name,
                    f_item.invoice_reference,
                    f_item.line_number or "Header",
                    f_item.item_code or "",
                    f_item.item_description or "",
                    f_item.finding_category,
                    f"{f_item.expected_amount:.2f}",
                    f"{f_item.invoiced_amount:.2f}",
                    f"{f_item.potential_difference:.2f}",
                    f_item.currency,
                    f_item.severity,
                    f_item.review_status,
                    f_item.calculation_explanation,
                    f_item.rule_version,
                    f_item.created_at.strftime("%Y-%m-%d %H:%M:%S") if f_item.created_at else "",
                    f_item.updated_at.strftime("%Y-%m-%d %H:%M:%S") if f_item.updated_at else ""
                ])

        return filename, filepath, len(findings), total_leakage

    def generate_pdf_report(
        self,
        case: ReconciliationCase,
        org: Organization,
        findings: List[Finding],
        documents: Optional[List[UploadedDocument]] = None,
        invoices: Optional[List[Invoice]] = None,
        contracts: Optional[List[Contract]] = None
    ) -> Tuple[str, str, int, Decimal]:
        """
        Generates a comprehensive landscape PDF report containing:
        - Executive Summary & Leakage Metrics
        - Evidence Documents Inventory
        - Extracted Line Items
        - Detailed Findings & Review Decisions
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"Reconciliation_{case.case_reference}_{timestamp}.pdf"
        filepath = os.path.join(self.export_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=landscape(letter),
            leftMargin=0.4 * inch,
            rightMargin=0.4 * inch,
            topMargin=0.4 * inch,
            bottomMargin=0.4 * inch
        )

        curr = findings[0].currency if findings else (case.currency or "GBP")
        curr_sym = get_currency_symbol(curr)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0f172a")
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#475569")
        )
        section_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontSize=11,
            leading=14,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1e293b")
        )
        cell_style = ParagraphStyle(
            "CellText",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#1e293b")
        )
        header_style = ParagraphStyle(
            "HeaderCell",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=9.5,
            fontName="Helvetica-Bold",
            textColor=colors.whitesmoke
        )

        elements = []

        # Header Title
        elements.append(Paragraph("<b>Contract & Invoice Reconciliation — Complete Audit Dossier</b>", title_style))
        supplier_str = f" | Supplier: <b>{case.supplier.name}</b>" if case.supplier else ""
        elements.append(Paragraph(
            f"Organization: <b>{org.name}</b> | Case: <b>{case.case_reference} — {case.title}</b>{supplier_str} | Generated: <b>{datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}</b>",
            subtitle_style
        ))
        elements.append(Spacer(1, 0.15 * inch))

        # 1. Executive Summary & Metrics Table
        total_potential = sum(f.potential_difference for f in findings)
        confirmed_findings = [f for f in findings if f.review_status == ReviewStatus.CONFIRMED.value]
        confirmed_leakage = sum(f.potential_difference for f in confirmed_findings)
        pending_findings = [f for f in findings if f.review_status == ReviewStatus.NEW.value]
        pending_leakage = sum(f.potential_difference for f in pending_findings)
        rejected_count = sum(1 for f in findings if f.review_status == ReviewStatus.REJECTED.value)

        summary_data = [
            ["Total Documents", "Total Invoiced Leakage", "Confirmed Leakage (Reviewed)", "Pending Review Leakage", "Total Exceptions"],
            [
                str(len(documents)) if documents else str(len(case.documents) if case.documents else 0),
                f"{curr_sym}{total_potential:,.2f}",
                f"{curr_sym}{confirmed_leakage:,.2f} ({len(confirmed_findings)} items)",
                f"{curr_sym}{pending_leakage:,.2f} ({len(pending_findings)} items)",
                f"{len(findings)} ({rejected_count} rejected)"
            ]
        ]
        summary_table = Table(summary_data, colWidths=[1.9 * inch, 2.1 * inch, 2.3 * inch, 2.2 * inch, 1.7 * inch])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, 1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.15 * inch))

        # 2. Documents Inventory Section
        docs_to_show = documents or (case.documents if hasattr(case, 'documents') else [])
        if docs_to_show:
            elements.append(Paragraph("<b>1. Evidence Documents Analyzed</b>", section_style))
            elements.append(Spacer(1, 0.05 * inch))

            doc_headers = [
                Paragraph("Filename", header_style),
                Paragraph("Category", header_style),
                Paragraph("Size", header_style),
                Paragraph("SHA-256 Hash", header_style),
                Paragraph("Extraction Status", header_style),
            ]
            doc_rows = [doc_headers]
            for d in docs_to_show:
                doc_rows.append([
                    Paragraph(f"<b>{d.original_filename}</b>", cell_style),
                    Paragraph(d.category.replace('_', ' '), cell_style),
                    Paragraph(f"{(d.file_size_bytes / 1024):.1f} KB", cell_style),
                    Paragraph(f"<font face='Courier'>{d.sha256_hash[:20]}...</font>", cell_style),
                    Paragraph(f"<font color='green'><b>{d.processing_status}</b></font>", cell_style),
                ])
            doc_table = Table(doc_rows, colWidths=[3.2 * inch, 1.8 * inch, 1.2 * inch, 2.5 * inch, 1.5 * inch])
            doc_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(doc_table)
            elements.append(Spacer(1, 0.15 * inch))

        # 3. Itemized Findings Table
        elements.append(Paragraph("<b>2. Reconciliation Leakage Findings & Exceptions</b>", section_style))
        elements.append(Spacer(1, 0.05 * inch))

        table_headers = [
            Paragraph("Ref / Invoice", header_style),
            Paragraph("Category", header_style),
            Paragraph("Item Description", header_style),
            Paragraph("Expected", header_style),
            Paragraph("Invoiced", header_style),
            Paragraph("Variance", header_style),
            Paragraph("Sev.", header_style),
            Paragraph("Review Status", header_style),
            Paragraph("Evidence & Explanation", header_style),
        ]
        table_rows = [table_headers]

        for f in findings:
            status_color = "#16a34a" if f.review_status == "CONFIRMED" else ("#dc2626" if f.review_status == "REJECTED" else "#d97706")
            table_rows.append([
                Paragraph(f"<b>{f.invoice_reference}</b><br/>Line: {f.line_number or '-'}", cell_style),
                Paragraph(f.finding_category.replace('_', ' '), cell_style),
                Paragraph(f.item_description or f.supplier_name, cell_style),
                Paragraph(f"{curr_sym}{f.expected_amount:,.2f}", cell_style),
                Paragraph(f"{curr_sym}{f.invoiced_amount:,.2f}", cell_style),
                Paragraph(f"<b>{curr_sym}{f.potential_difference:,.2f}</b>", cell_style),
                Paragraph(f.severity[:4], cell_style),
                Paragraph(f"<font color='{status_color}'><b>{f.review_status}</b></font>", cell_style),
                Paragraph(f.calculation_explanation[:200] + ("..." if len(f.calculation_explanation) > 200 else ""), cell_style),
            ])

        col_widths = [1.1 * inch, 1.4 * inch, 1.4 * inch, 0.9 * inch, 0.9 * inch, 1.0 * inch, 0.6 * inch, 1.0 * inch, 1.9 * inch]
        findings_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
        findings_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("ALIGN", (3, 1), (5, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(findings_table)

        doc.build(elements)
        return filename, filepath, len(findings), total_potential

    def generate_excel_report(
        self,
        case: ReconciliationCase,
        org: Organization,
        findings: List[Finding],
        documents: Optional[List[UploadedDocument]] = None,
        invoices: Optional[List[Invoice]] = None,
        contracts: Optional[List[Contract]] = None
    ) -> Tuple[str, str, int, Decimal]:
        """
        Generates a comprehensive multi-sheet Excel workbook (.xlsx):
        - Sheet 1: Executive Summary
        - Sheet 2: Findings & Exceptions
        - Sheet 3: Extracted Line Items
        - Sheet 4: Documents Analyzed
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"Reconciliation_{case.case_reference}_{timestamp}.xlsx"
        filepath = os.path.join(self.export_dir, filename)

        wb = openpyxl.Workbook()

        curr = findings[0].currency if findings else (case.currency or "GBP")
        curr_sym = get_currency_symbol(curr)
        total_potential = sum((f.potential_difference for f in findings), Decimal("0.00"))
        confirmed_leakage = sum((f.potential_difference for f in findings if f.review_status == ReviewStatus.CONFIRMED.value), Decimal("0.00"))
        pending_leakage = sum((f.potential_difference for f in findings if f.review_status == ReviewStatus.NEW.value), Decimal("0.00"))

        header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        title_font = Font(name="Arial", size=14, bold=True, color="0F172A")
        sub_font = Font(name="Arial", size=10, italic=True, color="475569")
        bold_font = Font(name="Arial", size=10, bold=True)
        regular_font = Font(name="Arial", size=9)
        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        # -------------------------------------------------------------
        # SHEET 1: Executive Summary
        # -------------------------------------------------------------
        ws_summary = wb.active
        ws_summary.title = "Executive Summary"
        ws_summary.views.sheetView[0].showGridLines = True

        ws_summary.append(["CONTRACT & INVOICE RECONCILIATION DOSSIER"])
        ws_summary["A1"].font = title_font
        ws_summary.append([f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"])
        ws_summary["A2"].font = sub_font
        ws_summary.append([])

        summary_rows = [
            ("Organization", org.name),
            ("Case Reference", case.case_reference),
            ("Case Title", case.title),
            ("Supplier Name", case.supplier.name if case.supplier else "N/A"),
            ("Case Currency", curr),
            ("Total Ingested Documents", len(documents) if documents else (len(case.documents) if case.documents else 0)),
            ("Total Findings Count", len(findings)),
            ("Total Invoiced Potential Leakage", f"{curr_sym}{total_potential:,.2f}"),
            ("Confirmed Leakage (Reviewed)", f"{curr_sym}{confirmed_leakage:,.2f}"),
            ("Pending Review Leakage", f"{curr_sym}{pending_leakage:,.2f}"),
            ("Reconciliation Status", case.status),
        ]
        for label, val in summary_rows:
            ws_summary.append([label, val])

        for row in ws_summary.iter_rows(min_row=4, max_row=4 + len(summary_rows) - 1, min_col=1, max_col=2):
            row[0].font = bold_font
            row[0].fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
            row[0].border = border_thin
            row[1].font = regular_font
            row[1].border = border_thin

        ws_summary.column_dimensions["A"].width = 30
        ws_summary.column_dimensions["B"].width = 45

        # -------------------------------------------------------------
        # SHEET 2: Findings & Exceptions
        # -------------------------------------------------------------
        ws_findings = wb.create_sheet(title="Findings & Exceptions")
        ws_findings.views.sheetView[0].showGridLines = True

        f_headers = [
            "Finding ID", "Invoice Ref", "Line #", "Supplier", "Category",
            "Item Code", "Item Description", "Expected", "Invoiced", "Variance",
            "Currency", "Severity", "Review Status", "Calculation Explanation"
        ]
        ws_findings.append(f_headers)
        for col_idx, _ in enumerate(f_headers, 1):
            cell = ws_findings.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for f in findings:
            ws_findings.append([
                f.id,
                f.invoice_reference,
                f.line_number or "Header",
                f.supplier_name,
                f.finding_category,
                f.item_code or "",
                f.item_description or "",
                float(f.expected_amount),
                float(f.invoiced_amount),
                float(f.potential_difference),
                f.currency,
                f.severity,
                f.review_status,
                f.calculation_explanation
            ])

        for row in ws_findings.iter_rows(min_row=2, max_row=1 + len(findings), min_col=1, max_col=len(f_headers)):
            for cell in row:
                cell.font = regular_font
                cell.border = border_thin

        # Column widths
        for col in ws_findings.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_findings.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

        # -------------------------------------------------------------
        # SHEET 3: Extracted Line Items
        # -------------------------------------------------------------
        ws_items = wb.create_sheet(title="Extracted Line Items")
        ws_items.views.sheetView[0].showGridLines = True

        inv_headers = ["Invoice Ref", "Line #", "Item Code", "Description", "Quantity", "Unit Price", "Line Total", "Currency"]
        ws_items.append(inv_headers)
        for col_idx, _ in enumerate(inv_headers, 1):
            cell = ws_items.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill

        invoices_to_show = invoices or (case.invoices if hasattr(case, 'invoices') else [])
        row_count = 0
        if invoices_to_show:
            for inv in invoices_to_show:
                for line in (inv.line_items or []):
                    ws_items.append([
                        inv.invoice_number,
                        line.line_number or "",
                        line.item_code or "",
                        line.description or "",
                        float(line.quantity) if line.quantity is not None else 0,
                        float(line.unit_price) if line.unit_price is not None else 0,
                        float(line.line_total) if line.line_total is not None else 0,
                        inv.currency
                    ])
                    row_count += 1

        for row in ws_items.iter_rows(min_row=2, max_row=1 + max(row_count, 1), min_col=1, max_col=len(inv_headers)):
            for cell in row:
                cell.font = regular_font
                cell.border = border_thin

        for col in ws_items.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_items.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 35)

        # -------------------------------------------------------------
        # SHEET 4: Documents Analyzed
        # -------------------------------------------------------------
        ws_docs = wb.create_sheet(title="Documents Analyzed")
        ws_docs.views.sheetView[0].showGridLines = True

        doc_headers = ["Filename", "Category", "File Type", "Size (KB)", "SHA-256 Hash", "Extraction Status", "Uploaded At"]
        ws_docs.append(doc_headers)
        for col_idx, _ in enumerate(doc_headers, 1):
            cell = ws_docs.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill

        docs_to_show = documents or (case.documents if hasattr(case, 'documents') else [])
        if docs_to_show:
            for d in docs_to_show:
                ws_docs.append([
                    d.original_filename,
                    d.category,
                    d.file_type,
                    round(d.file_size_bytes / 1024, 1),
                    d.sha256_hash,
                    d.processing_status,
                    d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else ""
                ])

        for row in ws_docs.iter_rows(min_row=2, max_row=1 + max(len(docs_to_show), 1), min_col=1, max_col=len(doc_headers)):
            for cell in row:
                cell.font = regular_font
                cell.border = border_thin

        for col in ws_docs.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_docs.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 35)

        wb.save(filepath)
        return filename, filepath, len(findings), total_potential

    def generate_json_dossier(
        self,
        case: ReconciliationCase,
        org: Organization,
        findings: List[Finding],
        documents: Optional[List[UploadedDocument]] = None,
        invoices: Optional[List[Invoice]] = None,
        contracts: Optional[List[Contract]] = None
    ) -> Tuple[str, str, int, Decimal]:
        """
        Generates full JSON audit dossier with all case data, documents, line items, and findings.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"Reconciliation_{case.case_reference}_{timestamp}.json"
        filepath = os.path.join(self.export_dir, filename)

        total_potential = sum((f.potential_difference for f in findings), Decimal("0.00"))
        confirmed_leakage = sum((f.potential_difference for f in findings if f.review_status == ReviewStatus.CONFIRMED.value), Decimal("0.00"))

        dossier = {
            "meta": {
                "generated_at": datetime.utcnow().isoformat(),
                "generator": "Contract & Invoice Leakage Finder v1.0",
                "format": "JSON_FULL_AUDIT_DOSSIER"
            },
            "organization": {
                "id": org.id,
                "name": org.name
            },
            "case": {
                "id": case.id,
                "case_reference": case.case_reference,
                "title": case.title,
                "supplier_name": case.supplier.name if case.supplier else None,
                "currency": case.currency,
                "status": case.status,
                "created_at": case.created_at.isoformat() if case.created_at else None
            },
            "summary_metrics": {
                "total_documents": len(documents) if documents else len(case.documents or []),
                "total_findings": len(findings),
                "total_potential_leakage": float(total_potential),
                "confirmed_leakage": float(confirmed_leakage),
                "currency": case.currency
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
                for d in (documents or case.documents or [])
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
            "invoices": [
                {
                    "id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "supplier_name": inv.supplier_name,
                    "currency": inv.currency,
                    "subtotal": float(inv.subtotal) if inv.subtotal is not None else 0,
                    "total_amount": float(inv.total_amount) if inv.total_amount is not None else 0,
                    "line_items": [
                        {
                            "id": li.id,
                            "line_number": li.line_number,
                            "item_code": li.item_code,
                            "description": li.description,
                            "quantity": float(li.quantity) if li.quantity is not None else 0,
                            "unit_price": float(li.unit_price) if li.unit_price is not None else 0,
                            "line_total": float(li.line_total) if li.line_total is not None else 0
                        }
                        for li in (inv.line_items or [])
                    ]
                }
                for inv in (invoices or case.invoices or [])
            ]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dossier, f, indent=2)

        return filename, filepath, len(findings), total_potential

report_generator = ReportGenerator()

