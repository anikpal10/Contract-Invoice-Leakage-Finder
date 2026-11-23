from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models.case import ReconciliationCase, CaseStatus
from backend.app.models.finding import Finding, FindingCategory, Severity, ReviewStatus, ReviewDecision
from backend.app.models.rule_config import RuleConfiguration
from backend.app.models.extracted_entities import (
    Contract, ContractLineItem,
    PurchaseOrder, POLineItem,
    Invoice, InvoiceLineItem,
    GoodsReceivedNote, GRNLineItem
)
from backend.app.models.document import UploadedDocument
from backend.app.services.matching import matching_service
from backend.app.services.normalization import normalization_service
from backend.app.services.llm_service import llm_service

TWO_PLACES = Decimal("0.01")
logger = logging.getLogger("leakage_finder.reconciliation")

def quantize_money(val: Decimal) -> Decimal:
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

class ReconciliationEngine:
    def run_reconciliation(
        self,
        db: Session,
        case: ReconciliationCase,
        reset_reviewed: bool = False
    ) -> List[Finding]:
        """
        Executes deterministic multi-way financial reconciliation across:
        Contracts, Price Schedules, Purchase Orders, Invoices, and GRNs.
        """
        # 1. Fetch active RuleConfiguration for organization
        rule_config = db.query(RuleConfiguration).filter(
            RuleConfiguration.organization_id == case.organization_id,
            RuleConfiguration.is_active == True
        ).order_by(RuleConfiguration.version.desc()).first()

        # Fallback default rule config if none created
        if not rule_config:
            rule_config = RuleConfiguration(
                organization_id=case.organization_id,
                version=1,
                price_variance_tolerance_pct=Decimal("0.00"),
                price_variance_tolerance_abs=Decimal("0.00"),
                quantity_variance_tolerance_pct=Decimal("0.00"),
                duplicate_window_days=90,
                fuzzy_match_threshold=85,
                high_severity_threshold=Decimal("500.00"),
                critical_severity_threshold=Decimal("2500.00"),
                require_grn_for_goods=True
            )

        # 2. Clear previous draft findings for this case if re-running
        if reset_reviewed:
            case_finding_ids = [r[0] for r in db.query(Finding.id).filter(Finding.case_id == case.id).all()]
            if case_finding_ids:
                db.query(ReviewDecision).filter(ReviewDecision.finding_id.in_(case_finding_ids)).delete(synchronize_session=False)
                db.query(Finding).filter(Finding.case_id == case.id).delete(synchronize_session=False)
                db.flush()
        else:
            db.query(Finding).filter(
                Finding.case_id == case.id,
                Finding.review_status == ReviewStatus.NEW.value
            ).delete()
            db.flush()

        invoices = case.invoices
        pos = case.purchase_orders
        contracts = case.contracts
        grns = case.goods_received_notes

        logger.info(
            "Reconciliation start | case_id=%s case_ref=%s case_currency=%s invoices=%d pos=%d contracts=%d grns=%d reset_reviewed=%s",
            case.id,
            case.case_reference,
            case.currency,
            len(invoices),
            len(pos),
            len(contracts),
            len(grns),
            reset_reviewed,
        )

        detected_currencies = {
            *(inv.currency for inv in invoices if inv.currency),
            *(po.currency for po in pos if po.currency),
            *(contract.currency for contract in contracts if contract.currency),
        }
        if len(detected_currencies) > 1:
            logger.warning(
                "Mixed currencies detected in case during reconciliation | case_id=%s currencies=%s",
                case.id,
                sorted(list(detected_currencies)),
            )

        findings: List[Finding] = []

        # 3. Check for Duplicate Invoices across current and past invoices
        duplicate_findings = self._check_duplicate_invoices(db, case, invoices, rule_config)
        findings.extend(duplicate_findings)

        # 4. Check each invoice
        for inv in invoices:
            sum_lines = quantize_money(sum((li.line_total for li in inv.line_items), Decimal("0.00"))) if inv.line_items else Decimal("0.00")
            logger.info(
                "Invoice basis snapshot | case_id=%s invoice=%s currency=%s subtotal=%s tax=%s total=%s line_sum=%s line_items=%d",
                case.id,
                inv.invoice_number,
                inv.currency,
                inv.subtotal,
                inv.tax_amount,
                inv.total_amount,
                sum_lines,
                len(inv.line_items or []),
            )

            # Check arithmetic consistency of invoice header
            total_findings = self._check_invoice_math(inv, rule_config)
            findings.extend(total_findings)

            # Match to Purchase Order
            matched_po = matching_service.match_invoice_to_po(inv, pos, rule_config.fuzzy_match_threshold)
            
            # Match to authorized Contract
            matched_contract = matching_service.match_invoice_to_contract(
                inv, contracts, rule_config.fuzzy_match_threshold
            )
            if matched_contract:
                logger.info(
                    "Invoice matched to contract | case_id=%s invoice=%s contract=%s supplier=%s",
                    case.id,
                    inv.invoice_number,
                    matched_contract.contract_reference,
                    matched_contract.supplier_name,
                )
            elif contracts:
                logger.warning(
                    "No matching contract found for invoice | case_id=%s invoice=%s contract_ref=%s supplier=%s",
                    case.id,
                    inv.invoice_number,
                    inv.contract_reference,
                    inv.supplier_name,
                )

            # Reconcile each invoice line item
            for inv_line in inv.line_items:
                # Math check: quantity * unit_price == line_total
                line_math_finding = self._check_line_math(inv, inv_line, rule_config)
                if line_math_finding:
                    findings.append(line_math_finding)

                # PO Price & Quantity Check
                if matched_po:
                    po_match = matching_service.match_invoice_line_to_po_line(
                        inv_line,
                        matched_po.line_items,
                        rule_config.fuzzy_match_threshold
                    )
                    if po_match:
                        po_line: POLineItem = po_match.matched_item
                        inv_line.matched_po_line_id = po_line.id
                        
                        # Check PO Unit Price mismatch
                        po_price_finding = self._check_po_price(inv, inv_line, matched_po, po_line, rule_config)
                        if po_price_finding:
                            findings.append(po_price_finding)

                        # Check Invoiced Quantity exceeding PO Quantity
                        po_qty_finding = self._check_po_quantity(inv, inv_line, matched_po, po_line, rule_config)
                        if po_qty_finding:
                            findings.append(po_qty_finding)

                # Contract Price Check
                if matched_contract:
                    contract_match = matching_service.match_invoice_line_to_contract_line(
                        inv_line,
                        matched_contract.line_items,
                        rule_config.fuzzy_match_threshold
                    )
                    if contract_match:
                        contract_line: ContractLineItem = contract_match.matched_item
                        inv_line.matched_contract_line_id = contract_line.id

                        # Check Contract Price Mismatch
                        contract_price_finding = self._check_contract_price(
                            inv, inv_line, matched_contract, contract_line, rule_config
                        )
                        if contract_price_finding:
                            findings.append(contract_price_finding)

                # Goods Received Note (GRN) Quantity Check
                if grns:
                    grn_finding = self._check_grn_quantity(inv, inv_line, grns, rule_config)
                    if grn_finding:
                        findings.append(grn_finding)

        # 5. Check for Potential Missing Credit Notes
        # If invoice references a return or credit adjustment that was not deducted
        missing_credit_findings = self._check_missing_credits(case, invoices, rule_config)
        findings.extend(missing_credit_findings)

        # Fetch existing human-reviewed findings (CONFIRMED, REJECTED, NEEDS_MORE_INFO)
        if reset_reviewed:
            existing_reviewed = []
            reviewed_keys = {}
            persisted_findings: List[Finding] = []
        else:
            existing_reviewed = db.query(Finding).filter(
                Finding.case_id == case.id,
                Finding.review_status != ReviewStatus.NEW.value
            ).all()

            reviewed_keys = {
                f"{f.finding_category}::{f.invoice_reference}::{f.line_number or ''}::{f.item_code or ''}": f
                for f in existing_reviewed
            }
            persisted_findings: List[Finding] = list(existing_reviewed)

        # Save and de-duplicate findings so no repeated items ever exist
        seen_keys = set()

        for f in findings:
            key = f"{f.finding_category}::{f.invoice_reference}::{f.line_number or ''}::{f.item_code or ''}"
            if key in reviewed_keys:
                # Already reviewed by human; do not create duplicate
                continue
            if key in seen_keys:
                # Duplicate within current run; skip
                continue
            seen_keys.add(key)
            db.add(f)
            persisted_findings.append(f)

        case.status = CaseStatus.RECONCILED.value
        logger.info(
            "Reconciliation complete | case_id=%s persisted_findings=%d deduped_runtime=%d",
            case.id,
            len(persisted_findings),
            len(findings) - len(seen_keys),
        )
        db.commit()
        return persisted_findings

    def _determine_severity(self, diff: Decimal, rule_config: RuleConfiguration) -> str:
        abs_diff = abs(diff)
        if abs_diff >= rule_config.critical_severity_threshold:
            return Severity.CRITICAL.value
        elif abs_diff >= rule_config.high_severity_threshold:
            return Severity.HIGH.value
        elif abs_diff >= Decimal("100.00"):
            return Severity.MEDIUM.value
        elif abs_diff > Decimal("0.00"):
            return Severity.LOW.value
        return Severity.INFO.value

    def _check_contract_price(
        self,
        inv: Invoice,
        inv_line: InvoiceLineItem,
        contract: Contract,
        contract_line: ContractLineItem,
        rule_config: RuleConfiguration
    ) -> Optional[Finding]:
        expected_price = contract_line.contracted_unit_price
        inv_price = inv_line.unit_price
        qty = inv_line.quantity

        price_diff = inv_price - expected_price
        if price_diff == Decimal("0.00"):
            return None  # Supplier billed exactly at the agreed contract price

        # Check tolerances on the absolute variance (applies to both over- and under-billing)
        abs_price_diff = abs(price_diff)
        if abs_price_diff <= rule_config.price_variance_tolerance_abs:
            return None
        if expected_price > Decimal("0.00"):
            pct_diff = (abs_price_diff / expected_price) * Decimal("100.0")
            if pct_diff <= rule_config.price_variance_tolerance_pct:
                return None

        expected_total = quantize_money(expected_price * qty)
        invoiced_total = quantize_money(inv_price * qty)
        potential_diff = quantize_money(invoiced_total - expected_total)

        is_undercharge = potential_diff < Decimal("0.00")
        category = (
            FindingCategory.POTENTIAL_UNDERCHARGE.value
            if is_undercharge
            else FindingCategory.CONTRACT_PRICE_MISMATCH.value
        )

        # Baseline deterministic calculation explanation
        if is_undercharge:
            explanation = (
                f"Potential undercharge detected. Contract '{contract.contract_reference}' stipulates "
                f"unit price of {inv.currency} {expected_price:.2f} for '{contract_line.description}', but "
                f"invoice '{inv.invoice_number}' billed at {inv.currency} {inv_price:.2f} per unit for quantity {qty:.0f}. "
                f"Potential undercharge difference: {inv.currency} {potential_diff:.2f}."
            )
        else:
            explanation = (
                f"Contract rate variance detected. Contract '{contract.contract_reference}' stipulates "
                f"unit price of {inv.currency} {expected_price:.2f} for '{contract_line.description}', but "
                f"invoice '{inv.invoice_number}' billed at {inv.currency} {inv_price:.2f} per unit for quantity {qty:.0f}. "
                f"Potential overcharge difference: {inv.currency} {potential_diff:.2f}."
            )

        # Deterministic audit explanation is generated instantly without remote network stalls
        doc_refs = [
            {
                "type": "INVOICE",
                "document_id": inv.document_id,
                "invoice_number": inv.invoice_number,
                "line_number": inv_line.line_number,
                "source": inv_line.source_page_or_row
            },
            {
                "type": "CONTRACT",
                "document_id": contract.document_id,
                "contract_reference": contract.contract_reference,
                "item_code": contract_line.item_code,
                "source": contract_line.source_page_or_row
            }
        ]

        return Finding(
            case_id=inv.case_id,
            organization_id=inv.case.organization_id,
            finding_category=category,
            supplier_name=inv.supplier_name,
            invoice_reference=inv.invoice_number,
            line_number=inv_line.line_number,
            item_code=inv_line.item_code,
            item_description=inv_line.description,
            expected_amount=expected_total,
            invoiced_amount=invoiced_total,
            potential_difference=potential_diff,
            currency=inv.currency,
            severity=self._determine_severity(potential_diff, rule_config),
            review_status=ReviewStatus.NEW.value,
            calculation_explanation=explanation,
            source_document_references=doc_refs,
            rule_version=rule_config.version
        )

    def _check_po_price(
        self,
        inv: Invoice,
        inv_line: InvoiceLineItem,
        po: PurchaseOrder,
        po_line: POLineItem,
        rule_config: RuleConfiguration
    ) -> Optional[Finding]:
        expected_price = po_line.unit_price
        inv_price = inv_line.unit_price
        qty = inv_line.quantity

        price_diff = inv_price - expected_price
        if price_diff == Decimal("0.00"):
            return None

        # Check tolerances on the absolute variance (applies to both over- and under-billing)
        abs_price_diff = abs(price_diff)
        if abs_price_diff <= rule_config.price_variance_tolerance_abs:
            return None
        if expected_price > Decimal("0.00"):
            pct_diff = (abs_price_diff / expected_price) * Decimal("100.0")
            if pct_diff <= rule_config.price_variance_tolerance_pct:
                return None

        expected_total = quantize_money(expected_price * qty)
        invoiced_total = quantize_money(inv_price * qty)
        potential_diff = quantize_money(invoiced_total - expected_total)

        is_undercharge = potential_diff < Decimal("0.00")
        category = (
            FindingCategory.POTENTIAL_UNDERCHARGE.value
            if is_undercharge
            else FindingCategory.PO_PRICE_MISMATCH.value
        )

        if is_undercharge:
            explanation = (
                f"Potential undercharge detected. Purchase order '{po.po_number}' authorised a unit price of "
                f"{inv.currency} {expected_price:.2f} for '{po_line.description}', whereas invoice "
                f"'{inv.invoice_number}' billed at {inv.currency} {inv_price:.2f} per unit for {qty:.0f} units. "
                f"Potential undercharge variance: {inv.currency} {potential_diff:.2f}."
            )
        else:
            explanation = (
                f"Purchase order price mismatch. PO '{po.po_number}' authorised a unit price of "
                f"{inv.currency} {expected_price:.2f} for '{po_line.description}', whereas invoice "
                f"'{inv.invoice_number}' billed at {inv.currency} {inv_price:.2f} per unit for {qty:.0f} units. "
                f"Variance: {inv.currency} {potential_diff:.2f}."
            )

        doc_refs = [
            {"type": "INVOICE", "document_id": inv.document_id, "invoice_number": inv.invoice_number, "line": inv_line.line_number},
            {"type": "PURCHASE_ORDER", "document_id": po.document_id, "po_number": po.po_number, "line": po_line.line_number}
        ]

        return Finding(
            case_id=inv.case_id,
            organization_id=inv.case.organization_id,
            finding_category=category,
            supplier_name=inv.supplier_name,
            invoice_reference=inv.invoice_number,
            line_number=inv_line.line_number,
            item_code=inv_line.item_code,
            item_description=inv_line.description,
            expected_amount=expected_total,
            invoiced_amount=invoiced_total,
            potential_difference=potential_diff,
            currency=inv.currency,
            severity=self._determine_severity(potential_diff, rule_config),
            review_status=ReviewStatus.NEW.value,
            calculation_explanation=explanation,
            source_document_references=doc_refs,
            rule_version=rule_config.version
        )

    def _check_po_quantity(
        self,
        inv: Invoice,
        inv_line: InvoiceLineItem,
        po: PurchaseOrder,
        po_line: POLineItem,
        rule_config: RuleConfiguration
    ) -> Optional[Finding]:
        ordered_qty = po_line.quantity
        invoiced_qty = inv_line.quantity

        qty_diff = invoiced_qty - ordered_qty
        if qty_diff <= Decimal("0.00"):
            return None

        # Check quantity tolerance
        if ordered_qty > Decimal("0.00"):
            pct_diff = (qty_diff / ordered_qty) * Decimal("100.0")
            if pct_diff <= rule_config.quantity_variance_tolerance_pct:
                return None

        expected_total = quantize_money(ordered_qty * inv_line.unit_price)
        invoiced_total = quantize_money(invoiced_qty * inv_line.unit_price)
        potential_diff = quantize_money(invoiced_total - expected_total)

        explanation = (
            f"Invoiced quantity exceeds ordered quantity. Purchase order '{po.po_number}' ordered "
            f"{ordered_qty:.0f} units of '{po_line.description}', but invoice '{inv.invoice_number}' "
            f"billed for {invoiced_qty:.0f} units (excess of {qty_diff:.0f} units at unit price {inv.currency} {inv_line.unit_price:.2f}). "
            f"Potential overbilled difference: {inv.currency} {potential_diff:.2f}."
        )

        doc_refs = [
            {"type": "INVOICE", "document_id": inv.document_id, "invoice_number": inv.invoice_number, "line": inv_line.line_number},
            {"type": "PURCHASE_ORDER", "document_id": po.document_id, "po_number": po.po_number, "line": po_line.line_number}
        ]

        return Finding(
            case_id=inv.case_id,
            organization_id=inv.case.organization_id,
            finding_category=FindingCategory.QUANTITY_OVER_PO.value,
            supplier_name=inv.supplier_name,
            invoice_reference=inv.invoice_number,
            line_number=inv_line.line_number,
            item_code=inv_line.item_code,
            item_description=inv_line.description,
            expected_amount=expected_total,
            invoiced_amount=invoiced_total,
            potential_difference=potential_diff,
            currency=inv.currency,
            severity=self._determine_severity(potential_diff, rule_config),
            review_status=ReviewStatus.NEW.value,
            calculation_explanation=explanation,
            source_document_references=doc_refs,
            rule_version=rule_config.version
        )

    def _check_grn_quantity(
        self,
        inv: Invoice,
        inv_line: InvoiceLineItem,
        grns: List[GoodsReceivedNote],
        rule_config: RuleConfiguration
    ) -> Optional[Finding]:
        # Sum total received across GRNs matching this item code/desc
        total_received = Decimal("0.00")
        grn_refs = []
        found_grn_match = False

        for grn in grns:
            for gli in grn.line_items:
                is_match = False
                if inv_line.item_code and gli.item_code:
                    if normalization_service.normalize_code(inv_line.item_code) == normalization_service.normalize_code(gli.item_code):
                        is_match = True
                elif normalization_service.calculate_similarity(inv_line.description, gli.description) >= 0.85:
                    is_match = True

                if is_match:
                    found_grn_match = True
                    total_received += gli.quantity_received
                    grn_refs.append({
                        "type": "GRN",
                        "document_id": grn.document_id,
                        "grn_number": grn.grn_number,
                        "quantity_received": float(gli.quantity_received)
                    })

        if not found_grn_match:
            return None

        qty_diff = inv_line.quantity - total_received
        if qty_diff <= Decimal("0.00"):
            return None

        expected_total = quantize_money(total_received * inv_line.unit_price)
        invoiced_total = quantize_money(inv_line.quantity * inv_line.unit_price)
        potential_diff = quantize_money(invoiced_total - expected_total)

        explanation = (
            f"Quantity billed exceeds goods received notes. Invoice '{inv.invoice_number}' billed for "
            f"{inv_line.quantity:.0f} units of '{inv_line.description}', but warehouse GRN records "
            f"confirm receipt of only {total_received:.0f} units (shortfall of {qty_diff:.0f} units). "
            f"Potential overbilling: {inv.currency} {potential_diff:.2f}."
        )

        doc_refs = [
            {"type": "INVOICE", "document_id": inv.document_id, "invoice_number": inv.invoice_number, "line": inv_line.line_number}
        ] + grn_refs

        return Finding(
            case_id=inv.case_id,
            organization_id=inv.case.organization_id,
            finding_category=FindingCategory.QUANTITY_OVER_GRN.value,
            supplier_name=inv.supplier_name,
            invoice_reference=inv.invoice_number,
            line_number=inv_line.line_number,
            item_code=inv_line.item_code,
            item_description=inv_line.description,
            expected_amount=expected_total,
            invoiced_amount=invoiced_total,
            potential_difference=potential_diff,
            currency=inv.currency,
            severity=self._determine_severity(potential_diff, rule_config),
            review_status=ReviewStatus.NEW.value,
            calculation_explanation=explanation,
            source_document_references=doc_refs,
            rule_version=rule_config.version
        )

    def _check_duplicate_invoices(
        self,
        db: Session,
        case: ReconciliationCase,
        invoices: List[Invoice],
        rule_config: RuleConfiguration
    ) -> List[Finding]:
        findings = []
        seen_numbers: Dict[str, Invoice] = {}

        for inv in invoices:
            norm_num = normalization_service.normalize_code(inv.invoice_number)
            norm_sup = normalization_service.normalize_supplier_name(inv.supplier_name)
            key = f"{norm_sup}::{norm_num}"

            if key in seen_numbers:
                original_inv = seen_numbers[key]
                # Only flag as duplicate if they come from different physical document files
                if original_inv.document_id == inv.document_id or original_inv.id == inv.id:
                    continue
                potential_diff = quantize_money(inv.total_amount)
                explanation = (
                    f"Duplicate invoice detected. Invoice '{inv.invoice_number}' from supplier '{inv.supplier_name}' "
                    f"for amount {inv.currency} {inv.total_amount:.2f} was already uploaded and billed under invoice ID "
                    f"'{original_inv.invoice_number}'. Potential duplicate exposure: {inv.currency} {potential_diff:.2f}."
                )

                findings.append(Finding(
                    case_id=case.id,
                    organization_id=case.organization_id,
                    finding_category=FindingCategory.DUPLICATE_INVOICE.value,
                    supplier_name=inv.supplier_name,
                    invoice_reference=inv.invoice_number,
                    expected_amount=Decimal("0.00"),
                    invoiced_amount=inv.total_amount,
                    potential_difference=potential_diff,
                    currency=inv.currency,
                    severity=self._determine_severity(potential_diff, rule_config),
                    review_status=ReviewStatus.NEW.value,
                    calculation_explanation=explanation,
                    source_document_references=[
                        {"type": "INVOICE_DUPLICATE", "document_id": inv.document_id, "invoice": inv.invoice_number},
                        {"type": "INVOICE_ORIGINAL", "document_id": original_inv.document_id, "invoice": original_inv.invoice_number}
                    ],
                    rule_version=rule_config.version
                ))
            else:
                seen_numbers[key] = inv

        return findings

    def _check_line_math(
        self,
        inv: Invoice,
        inv_line: InvoiceLineItem,
        rule_config: RuleConfiguration
    ) -> Optional[Finding]:
        # Both quantity and unit price must be extracted and non-zero to evaluate arithmetic validity
        qty = inv_line.quantity or Decimal("0.00")
        price = inv_line.unit_price or Decimal("0.00")
        if qty <= Decimal("0.00") or price <= Decimal("0.00"):
            return None

        expected_line_total = quantize_money(qty * price)
        actual_line_total = quantize_money(inv_line.line_total or Decimal("0.00"))
        diff = actual_line_total - expected_line_total

        if abs(diff) > Decimal("0.05"):  # Allow trivial 5p rounding differences
            explanation = (
                f"Invoice line arithmetic mismatch. Line {inv_line.line_number} for '{inv_line.description}' "
                f"shows quantity {inv_line.quantity:.2f} × unit price {inv.currency} {inv_line.unit_price:.2f} = "
                f"expected {inv.currency} {expected_line_total:.2f}, but line total is stated as {inv.currency} {actual_line_total:.2f}. "
                f"Calculation difference: {inv.currency} {diff:.2f}."
            )

            return Finding(
                case_id=inv.case_id,
                organization_id=inv.case.organization_id,
                finding_category=FindingCategory.INCORRECT_LINE_TOTAL.value,
                supplier_name=inv.supplier_name,
                invoice_reference=inv.invoice_number,
                line_number=inv_line.line_number,
                item_code=inv_line.item_code,
                item_description=inv_line.description,
                expected_amount=expected_line_total,
                invoiced_amount=actual_line_total,
                potential_difference=abs(diff),
                currency=inv.currency,
                severity=self._determine_severity(abs(diff), rule_config),
                review_status=ReviewStatus.NEW.value,
                calculation_explanation=explanation,
                source_document_references=[
                    {"type": "INVOICE", "document_id": inv.document_id, "invoice_number": inv.invoice_number, "line": inv_line.line_number}
                ],
                rule_version=rule_config.version
            )
        return None

    def _check_invoice_math(
        self,
        inv: Invoice,
        rule_config: RuleConfiguration
    ) -> List[Finding]:
        findings = []
        if not inv.line_items:
            return findings

        # Sum lines
        sum_lines = sum(quantize_money(li.line_total) for li in inv.line_items)
        stated_subtotal = quantize_money(inv.subtotal) if inv.subtotal is not None else None

        # Requirement 3 & 4: Never treat a missing subtotal as zero. Calculate from validated line items.
        if stated_subtotal is None or stated_subtotal <= Decimal("0.00"):
            if sum_lines > Decimal("0.00"):
                # Missing subtotal is derived from validated line items
                inv.subtotal = sum_lines
                if inv.total_amount is None or inv.total_amount <= Decimal("0.00"):
                    inv.total_amount = sum_lines + (inv.tax_amount or Decimal("0.00"))
            return findings

        # A true subtotal mismatch only occurs if the document explicitly stated a non-zero subtotal
        # that differs from the sum of its validated line item totals.
        if abs(stated_subtotal - sum_lines) > Decimal("0.10"):
            diff = abs(stated_subtotal - sum_lines)
            explanation = (
                f"Invoice subtotal mismatch. Sum of individual line totals is {inv.currency} {sum_lines:.2f}, "
                f"whereas stated invoice subtotal is {inv.currency} {stated_subtotal:.2f}. "
                f"Difference: {inv.currency} {diff:.2f}."
            )
            findings.append(Finding(
                case_id=inv.case_id,
                organization_id=inv.case.organization_id,
                finding_category=FindingCategory.INCORRECT_INVOICE_TOTAL.value,
                supplier_name=inv.supplier_name,
                invoice_reference=inv.invoice_number,
                expected_amount=sum_lines,
                invoiced_amount=stated_subtotal,
                potential_difference=diff,
                currency=inv.currency,
                severity=self._determine_severity(diff, rule_config),
                review_status=ReviewStatus.NEW.value,
                calculation_explanation=explanation,
                source_document_references=[{
                    "type": "INVOICE",
                    "document_id": inv.document_id,
                    "invoice_number": inv.invoice_number,
                    "is_aggregate": True
                }],
                rule_version=rule_config.version
            ))

        return findings

    def _check_missing_credits(
        self,
        case: ReconciliationCase,
        invoices: List[Invoice],
        rule_config: RuleConfiguration
    ) -> List[Finding]:
        findings = []
        for inv in invoices:
            if inv.is_credit_note:
                # Credit note is present and identified
                continue
            # If notes or line items indicate returned goods without an applied credit note
            for li in inv.line_items:
                if "return" in li.description.lower() or "credit" in li.description.lower():
                    if li.line_total > Decimal("0.00"):
                        explanation = (
                            f"Potentially missing or inverted credit. Line '{li.description}' on invoice "
                            f"'{inv.invoice_number}' appears to reference a credit/return adjustment but was "
                            f"billed as a positive charge ({inv.currency} {li.line_total:.2f}) instead of a credit deduction."
                        )
                        findings.append(Finding(
                            case_id=case.id,
                            organization_id=case.organization_id,
                            finding_category=FindingCategory.MISSING_CREDIT_OR_AMENDMENT.value,
                            supplier_name=inv.supplier_name,
                            invoice_reference=inv.invoice_number,
                            line_number=li.line_number,
                            expected_amount=-li.line_total,
                            invoiced_amount=li.line_total,
                            potential_difference=li.line_total * Decimal("2.0"),
                            currency=inv.currency,
                            severity=self._determine_severity(li.line_total, rule_config),
                            review_status=ReviewStatus.NEW.value,
                            calculation_explanation=explanation,
                            source_document_references=[{"type": "INVOICE", "document_id": inv.document_id, "line": li.line_number}],
                            rule_version=rule_config.version
                        ))
        return findings

reconciliation_engine = ReconciliationEngine()
