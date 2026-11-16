import os
import json
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.schemas.llm_extraction import (
    ExtractedDocumentData,
    ExtractedLineItem,
    LLMMatchResult,
    LLMLeakageAnalysis
)

logger = logging.getLogger("leakage_finder.llm_service")

class LLMService:
    def __init__(self):
        self.gemini_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        self.openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY", "")
        self.provider = settings.LLM_PROVIDER.lower() if hasattr(settings, "LLM_PROVIDER") else "gemini"
        
        self.gemini_client = None
        self.openai_client = None
        self._billing_disabled = False

        if self.gemini_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.gemini_key)
                logger.info("Google GenAI client initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI client: {e}")

        if self.openai_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_key)
                logger.info("OpenAI client initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")

    def is_available(self) -> bool:
        return self.gemini_client is not None or self.openai_client is not None

    def get_active_provider_name(self) -> str:
        if self.gemini_client:
            return f"Google Gemini ({settings.GEMINI_MODEL})"
        if self.openai_client:
            return f"OpenAI ({settings.OPENAI_MODEL})"
        return "Deterministic Fallback (No LLM API key configured)"

    def _call_raw_llm(self, system_instruction: str, user_prompt: str) -> Optional[str]:
        """
        Executes raw generation on the active LLM provider.
        """
        # Try Gemini first if configured
        if self.gemini_client and not self._billing_disabled:
            try:
                full_prompt = f"{system_instruction}\n\n{user_prompt}"
                response = self.gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=full_prompt,
                )
                text = response.text.strip()
                return self._clean_json_markdown(text)
            except Exception as e:
                err_str = str(e)
                if "403" in err_str or "PERMISSION_DENIED" in err_str or "billing" in err_str.lower():
                    self._billing_disabled = True
                    logger.warning(f"Gemini API billing/permission error — falling back to heuristic extraction: {e}")
                else:
                    logger.error(f"Gemini API generation error: {e}")

        # Fallback to OpenAI if configured
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"} if "json" in system_instruction.lower() else None,
                    temperature=0.1
                )
                text = response.choices[0].message.content or ""
                return self._clean_json_markdown(text)
            except Exception as e:
                logger.error(f"OpenAI API invocation error: {e}")

        return None

    def _clean_json_markdown(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def extract_document_information(
        self,
        document_text: str,
        category: str,
        filename: str
    ) -> Optional[ExtractedDocumentData]:
        """
        Uses LLM to extract financial fields and structured items from document text.
        Validates output using Pydantic.
        """
        if not self.is_available():
            return None

        system_prompt = """
You are an expert financial auditor and data extraction engine.
Your task is to analyze document text and extract accurate financial information.

CRITICAL RULES:
1. NEVER invent, hallucinate, or fabricate missing prices, quantities, dates, or references.
2. If any field or detail is not present in the text, set it to null.
3. Every line item must include product_name, quantity, unit_price, source_page_number, text_evidence, and confidence_score.
4. Output MUST be valid JSON conforming strictly to the requested schema.
"""

        user_prompt = f"""
DOCUMENT FILE: {filename}
CATEGORY: {category}

Extract all financial details and line items into JSON with this exact schema:
{{
  "document_category": "{category.upper()}",
  "reference_number": "Invoice/PO/Contract Reference",
  "supplier_name": "Supplier or Vendor Name",
  "document_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "contract_validity_start": "YYYY-MM-DD or null",
  "contract_validity_end": "YYYY-MM-DD or null",
  "payment_terms": "e.g. Net 30 or null",
  "currency": "GBP or EUR or USD or INR",
  "subtotal": 1000.0,
  "tax_amount": 200.0,
  "discount_amount": 0.0,
  "total_amount": 1200.0,
  "po_reference": "PO-1234 or null",
  "contract_reference": "CTR-1234 or null",
  "confidence_score": 0.95,
  "line_items": [
    {{
      "line_number": 1,
      "product_name": "Item Name",
      "product_description": "Item Description",
      "quantity": 10.0,
      "unit_price": 50.0,
      "total_price": 500.0,
      "tax_amount": 100.0,
      "discount": 0.0,
      "currency": "GBP",
      "source_page_number": 1,
      "text_evidence": "Verbatim quote or evidence from text",
      "confidence_score": 0.95
    }}
  ]
}}

DOCUMENT TEXT:
\"\"\"
{document_text}
\"\"\"
"""
        raw_json = self._call_raw_llm(system_prompt, user_prompt)
        if not raw_json:
            return None

        try:
            data_dict = json.loads(raw_json)
            # Validate with Pydantic
            validated = ExtractedDocumentData.model_validate(data_dict)
            return validated
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"LLM extraction validation error: {e}")
            return None

    def extract_document_from_pdf_multimodal(
        self,
        pdf_path: str,
        category: str,
        filename: str
    ) -> Optional[ExtractedDocumentData]:
        """
        Uses Gemini multimodal vision capabilities to extract structured financial data
        directly from PDF bytes (ideal for scanned documents or complex visual tables).
        """
        if not self.gemini_client or self._billing_disabled or not os.path.exists(pdf_path):
            return None

        try:
            from google.genai import types
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            pdf_part = types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf"
            )

            prompt = f"""
You are an expert financial auditor performing OCR and data extraction on this uploaded document.
DOCUMENT FILENAME: {filename}
CATEGORY: {category}

CRITICAL RULES:
1. NEVER invent, hallucinate, or fabricate missing prices, quantities, dates, or references.
2. If any field or detail is not present in the document, set it to null.
3. Every line item must include product_name, quantity, unit_price, source_page_number, text_evidence, and confidence_score.
4. Output MUST be valid JSON conforming strictly to the requested schema.

Extract all financial details and line items into JSON with this exact schema:
{{
  "document_category": "{category.upper()}",
  "reference_number": "Invoice/PO/Contract Reference",
  "supplier_name": "Supplier or Vendor Name",
  "document_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "contract_validity_start": "YYYY-MM-DD or null",
  "contract_validity_end": "YYYY-MM-DD or null",
  "payment_terms": "e.g. Net 30 or null",
  "currency": "GBP or EUR or USD or INR",
  "subtotal": 1000.0,
  "tax_amount": 200.0,
  "discount_amount": 0.0,
  "total_amount": 1200.0,
  "po_reference": "PO-1234 or null",
  "contract_reference": "CTR-1234 or null",
  "confidence_score": 0.95,
  "line_items": [
    {{
      "line_number": 1,
      "product_name": "Item Name",
      "product_description": "Item Description",
      "quantity": 10.0,
      "unit_price": 50.0,
      "total_price": 500.0,
      "tax_amount": 100.0,
      "discount": 0.0,
      "currency": "GBP",
      "source_page_number": 1,
      "text_evidence": "Verbatim quote or visual evidence from document",
      "confidence_score": 0.95
    }}
  ]
}}
Never invent or guess numbers. Return ONLY valid JSON.
"""
            response = self.gemini_client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[pdf_part, prompt]
            )
            raw_text = self._clean_json_markdown(response.text.strip())
            data_dict = json.loads(raw_text)
            return ExtractedDocumentData.model_validate(data_dict)
        except Exception as e:
            err_str = str(e)
            if "403" in err_str or "PERMISSION_DENIED" in err_str or "billing" in err_str.lower():
                self._billing_disabled = True
                logger.warning(f"Gemini multimodal billing/permission error — falling back to heuristic: {e}")
            else:
                logger.warning(f"Gemini multimodal PDF extraction error: {e}")
            return None

    def match_products_semantic(
        self,
        invoice_item_desc: str,
        invoice_item_code: Optional[str],
        candidate_contract_items: List[Dict[str, Any]]
    ) -> LLMMatchResult:
        """
        Uses LLM to match an invoice line item description with contract candidate items,
        handling differently worded product descriptions, abbreviations, and specifications.
        """
        if not self.is_available() or not candidate_contract_items:
            # Deterministic fallback match
            return LLMMatchResult(
                is_match=False,
                invoice_item_description=invoice_item_desc,
                confidence_score=0.0,
                reasoning="LLM not configured or no candidate contract items available.",
                requires_human_review=True
            )

        system_prompt = """
You are a senior procurement auditor specializing in product matching between supplier contracts and invoices.
Compare the invoice item against the agreed contract items.
Determine whether the invoice item represents the same product or service as any contract item,
accounting for synonyms, abbreviations, brand names, and minor phrasing variations.

RULES:
1. Do NOT automatically assume similar names are the same item if specifications differ (e.g. 16GB vs 32GB RAM).
2. If uncertain, assign a confidence below 0.85 and set requires_human_review to true.
3. Return valid JSON only.
"""

        candidates_formatted = json.dumps(candidate_contract_items, indent=2)
        user_prompt = f"""
INVOICE ITEM:
Description: "{invoice_item_desc}"
Item Code: "{invoice_item_code or 'N/A'}"

CONTRACT CANDIDATE ITEMS:
{candidates_formatted}

Identify the best matching contract item. Respond with JSON:
{{
  "is_match": true/false,
  "matched_contract_line_id": "UUID of matched item or null",
  "contract_item_description": "Description of matched item or null",
  "confidence_score": 0.95,
  "reasoning": "Detailed justification for the match or non-match",
  "requires_human_review": false
}}
"""
        raw_json = self._call_raw_llm(system_prompt, user_prompt)
        if raw_json:
            try:
                res_dict = json.loads(raw_json)
                res_dict["invoice_item_description"] = invoice_item_desc
                return LLMMatchResult.model_validate(res_dict)
            except Exception as e:
                logger.warning(f"Error parsing LLM product match: {e}")

        return LLMMatchResult(
            is_match=False,
            invoice_item_description=invoice_item_desc,
            confidence_score=0.0,
            reasoning="Failed to obtain structured LLM match decision.",
            requires_human_review=True
        )

    def analyze_leakage_finding(
        self,
        finding_category: str,
        supplier_name: str,
        invoice_ref: str,
        product_name: str,
        contract_ref: str,
        agreed_price: Decimal,
        invoiced_price: Decimal,
        quantity: Decimal,
        cost_difference: Decimal,
        currency: str,
        contract_validity: Optional[str] = None
    ) -> str:
        """
        Generates clear, auditor-grade natural language explanation for why a transaction was flagged.
        """
        if not self.is_available():
            return (
                f"Rate discrepancy: Contract '{contract_ref}' specifies {currency} {agreed_price:.2f} for '{product_name}', "
                f"but invoice '{invoice_ref}' billed at {currency} {invoiced_price:.2f} (qty: {quantity:.0f}). "
                f"Total potential leakage: {currency} {cost_difference:.2f}."
            )

        system_prompt = """
You are a forensic financial auditor writing an executive findings explanation for an Accounts Payable Audit committee.
Explain clearly and objectively why this charge constitutes potential financial leakage.
Never accuse the supplier of intentional fraud; state evidence and contract terms neutrally.
"""

        user_prompt = f"""
FINDING DETAILS:
- Category: {finding_category}
- Supplier: {supplier_name}
- Invoice Reference: {invoice_ref}
- Product: {product_name}
- Contract Reference: {contract_ref}
- Contract Agreed Unit Price: {currency} {agreed_price:.2f}
- Invoiced Unit Price: {currency} {invoiced_price:.2f}
- Billed Quantity: {quantity}
- Expected Amount: {currency} {agreed_price * quantity:.2f}
- Invoiced Amount: {currency} {invoiced_price * quantity:.2f}
- Cost Difference (Potential Leakage): {currency} {cost_difference:.2f}
- Contract Validity: {contract_validity or 'Active'}

Write a concise 2-3 sentence executive audit explanation detailing the variance, calculation, and recommended reviewer verification.
"""
        explanation = self._call_raw_llm(system_prompt, user_prompt)
        if explanation and len(explanation) > 20:
            return explanation.strip().replace('"', '')

        return (
            f"Contract rate variance detected. Contract '{contract_ref}' stipulates "
            f"unit price of {currency} {agreed_price:.2f} for '{product_name}', but "
            f"invoice '{invoice_ref}' billed at {currency} {invoiced_price:.2f} per unit for quantity {quantity:.0f}. "
            f"Potential overcharge difference: {currency} {cost_difference:.2f}."
        )

llm_service = LLMService()
