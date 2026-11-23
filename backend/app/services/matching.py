import re
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.extracted_entities import (
    Contract, ContractLineItem,
    PurchaseOrder, POLineItem,
    Invoice, InvoiceLineItem,
    GoodsReceivedNote, GRNLineItem
)
from backend.app.services.normalization import normalization_service
from backend.app.services.llm_service import llm_service

class MatchResult:
    def __init__(
        self,
        matched_item: Any,
        match_type: str,  # EXACT_CODE, EXACT_DESC, FUZZY_DESC, PO_REFERENCE
        confidence: float,
        notes: str = ""
    ):
        self.matched_item = matched_item
        self.match_type = match_type
        self.confidence = confidence
        self.notes = notes

class MatchingService:
    def match_invoice_to_po(
        self,
        invoice: Invoice,
        pos: List[PurchaseOrder],
        fuzzy_threshold: int = 85
    ) -> Optional[PurchaseOrder]:
        """
        Matches invoice to a purchase order via reference or supplier matching.
        """
        if not pos:
            return None

        # 1. Exact PO reference matching
        if invoice.po_reference:
            norm_inv_po = normalization_service.normalize_code(invoice.po_reference)
            for po in pos:
                if normalization_service.normalize_code(po.po_number) == norm_inv_po:
                    return po

        # 2. Supplier name match if single PO in case
        if len(pos) == 1:
            inv_supplier = normalization_service.normalize_supplier_name(invoice.supplier_name)
            po_supplier = normalization_service.normalize_supplier_name(pos[0].supplier_name)
            if inv_supplier == po_supplier or normalization_service.calculate_similarity(inv_supplier, po_supplier) >= 0.8:
                return pos[0]

        return None

    def match_invoice_to_contract(
        self,
        invoice: Invoice,
        contracts: List[Contract],
        fuzzy_threshold: int = 80
    ) -> Optional[Contract]:
        """
        Matches invoice to the authorized contract based on:
        1. Exact or substring match on contract_reference (e.g. CON-2026-044)
        2. Supplier name matching with currency consistency
        """
        if not contracts:
            return None

        # 1. Match by contract_reference if present on invoice
        if invoice.contract_reference:
            norm_inv_ref = normalization_service.normalize_code(invoice.contract_reference)
            for c in contracts:
                norm_c_ref = normalization_service.normalize_code(c.contract_reference)
                if norm_c_ref == norm_inv_ref or norm_c_ref in norm_inv_ref or norm_inv_ref in norm_c_ref:
                    return c

        # 2. Match by supplier_name
        inv_supplier = normalization_service.normalize_supplier_name(invoice.supplier_name or "")
        inv_curr = (invoice.currency or "").upper()

        if inv_supplier:
            # Look for exact supplier match with compatible currency
            for c in contracts:
                c_supplier = normalization_service.normalize_supplier_name(c.supplier_name or "")
                c_curr = (c.currency or "").upper()
                if inv_supplier == c_supplier:
                    if not inv_curr or not c_curr or inv_curr == c_curr:
                        return c

            # Fuzzy supplier match
            best_match = None
            best_score = 0.0
            for c in contracts:
                c_supplier = normalization_service.normalize_supplier_name(c.supplier_name or "")
                score = normalization_service.calculate_similarity(inv_supplier, c_supplier)
                if score > best_score:
                    best_score = score
                    best_match = c

            if best_match and (best_score * 100) >= fuzzy_threshold:
                return best_match

        # 3. If there is only 1 contract in the case and currency matches, match it
        if len(contracts) == 1:
            c = contracts[0]
            c_curr = (c.currency or "").upper()
            if not inv_curr or not c_curr or inv_curr == c_curr:
                return c

        return None

    def match_invoice_line_to_po_line(
        self,
        inv_line: InvoiceLineItem,
        po_lines: List[POLineItem],
        fuzzy_threshold: int = 85
    ) -> Optional[MatchResult]:
        if not po_lines:
            return None

        # 1. Exact Item Code match
        if inv_line.item_code:
            norm_inv_code = normalization_service.normalize_code(inv_line.item_code)
            for poli in po_lines:
                if poli.item_code and normalization_service.normalize_code(poli.item_code) == norm_inv_code:
                    return MatchResult(poli, "EXACT_CODE", 1.0, f"Exact item code match '{inv_line.item_code}'")

        # 2. Exact normalized description match
        norm_inv_desc = normalization_service.normalize_description(inv_line.description)
        for poli in po_lines:
            if normalization_service.normalize_description(poli.description) == norm_inv_desc:
                return MatchResult(poli, "EXACT_DESC", 0.98, "Exact normalized description match")

        # 3. Fuzzy description match
        best_match = None
        best_score = 0.0
        for poli in po_lines:
            score = normalization_service.calculate_similarity(
                inv_line.description,
                poli.description
            )
            if score > best_score:
                best_score = score
                best_match = poli

        if best_match and (best_score * 100) >= fuzzy_threshold:
            return MatchResult(
                best_match,
                "FUZZY_DESC",
                best_score,
                f"Fuzzy description match ({int(best_score * 100)}% similarity)"
            )

        return None

    def match_invoice_line_to_contract_line(
        self,
        inv_line: InvoiceLineItem,
        contract_lines: List[ContractLineItem],
        fuzzy_threshold: int = 85
    ) -> Optional[MatchResult]:
        if not contract_lines:
            return None

        # 1. Exact Item Code (validated with description to prevent generic synthetic ITEM-XX collisions)
        if inv_line.item_code:
            norm_inv_code = normalization_service.normalize_code(inv_line.item_code)
            is_synthetic_code = bool(re.match(r"^(?:ITEM|LINE|GEN|PART)[-_]?\d+$", norm_inv_code, re.IGNORECASE))
            for cli in contract_lines:
                if cli.item_code and normalization_service.normalize_code(cli.item_code) == norm_inv_code:
                    desc_sim = normalization_service.calculate_similarity(inv_line.description, cli.description)
                    # If it's a synthetic generic code and descriptions completely differ, do not false-match
                    if is_synthetic_code and desc_sim < 0.30:
                        continue
                    return MatchResult(cli, "EXACT_CODE", 1.0, f"Exact contract item code '{inv_line.item_code}'")

        # 2. Exact Description
        norm_inv_desc = normalization_service.normalize_description(inv_line.description)
        for cli in contract_lines:
            if normalization_service.normalize_description(cli.description) == norm_inv_desc:
                return MatchResult(cli, "EXACT_DESC", 0.98, "Exact contract description match")

        # 3. Fuzzy description (evaluates both sort ratio and subset token ratio)
        best_match = None
        best_score = 0.0
        for cli in contract_lines:
            if not cli.description:
                continue
            sim_sort = normalization_service.calculate_similarity(inv_line.description, cli.description)
            sim_set = normalization_service.calculate_token_set_similarity(inv_line.description, cli.description)
            score = max(sim_sort, sim_set)
            if score > best_score:
                best_score = score
                best_match = cli

        if best_match and (best_score * 100) >= fuzzy_threshold:
            return MatchResult(
                best_match,
                "FUZZY_DESC",
                best_score,
                f"Fuzzy contract description match ({int(best_score * 100)}%)"
            )

        # 4. LLM Semantic Product Matching (interpreting differently worded product descriptions)
        if llm_service.is_available():
            candidate_dicts = [
                {
                    "contract_line_id": cli.id,
                    "item_code": cli.item_code or "N/A",
                    "description": cli.description,
                    "contracted_unit_price": float(cli.contracted_unit_price) if cli.contracted_unit_price else 0.0
                }
                for cli in contract_lines
            ]
            llm_result = llm_service.match_products_semantic(
                invoice_item_desc=inv_line.description,
                invoice_item_code=inv_line.item_code,
                candidate_contract_items=candidate_dicts
            )
            if llm_result.is_match and llm_result.matched_contract_line_id:
                for cli in contract_lines:
                    if cli.id == llm_result.matched_contract_line_id:
                        return MatchResult(
                            matched_item=cli,
                            match_type="LLM_SEMANTIC_MATCH",
                            confidence=llm_result.confidence_score,
                            notes=f"LLM match: {llm_result.reasoning}"
                        )

        return None

matching_service = MatchingService()

