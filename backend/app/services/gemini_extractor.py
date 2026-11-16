import os
import json
import re
from typing import Dict, Any, Optional
from backend.app.core.config import settings

class GeminiExtractor:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = settings.GEMINI_MODEL
        self.client = None
        self._billing_disabled = False
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Google GenAI client: {e}")
                self.client = None

    def is_gemini_active(self) -> bool:
        return self.client is not None and not self._billing_disabled

    def extract_document_with_gemini(
        self,
        document_text: str,
        category: str,
        filename: str
    ) -> Optional[Dict[str, Any]]:
        """
        Calls Gemini API with structured prompt and JSON response format.
        """
        if not self.is_gemini_active():
            return None

        prompt = f"""
You are an expert financial auditor extracting structured data from business documents.
Analyze the following document text from file '{filename}' which is categorized as '{category}'.

RULES:
1. NEVER invent, fabricate, or guess missing information.
2. If a field is not present in the text, return null.
3. For all numbers (prices, quantities, amounts), extract the exact numerical value without currency symbols.
4. Extract every single line item accurately.
5. Provide a confidence score (between 0.0 and 1.0) for every extracted field and line item.
6. Return ONLY valid JSON matching this structure:

For INVOICE:
{{
  "invoice_number": "INV-12345",
  "supplier_name": "Supplier Name",
  "invoice_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "po_reference": "PO-9999",
  "contract_reference": "CTR-001",
  "currency": "GBP",
  "subtotal": 5000.00,
  "tax_amount": 1000.00,
  "total_amount": 6000.00,
  "is_credit_note": false,
  "confidence": 0.95,
  "line_items": [
    {{
      "line_number": 1,
      "item_code": "ITEM-1",
      "description": "Description",
      "quantity": 100.0,
      "unit_price": 50.0,
      "line_total": 5000.0,
      "tax_rate": 20.0,
      "source_page_or_row": "Page 1",
      "confidence": 0.95
    }}
  ]
}}

For PURCHASE_ORDER:
{{
  "po_number": "PO-9999",
  "supplier_name": "Supplier Name",
  "order_date": "YYYY-MM-DD",
  "currency": "GBP",
  "total_amount": 5000.00,
  "confidence": 0.95,
  "line_items": [
    {{
      "line_number": 1,
      "item_code": "ITEM-1",
      "description": "Description",
      "quantity": 100.0,
      "unit_price": 50.0,
      "line_total": 5000.0,
      "source_page_or_row": "Page 1",
      "confidence": 0.95
    }}
  ]
}}

For CONTRACT or PRICE_SCHEDULE:
{{
  "contract_reference": "CTR-001",
  "supplier_name": "Supplier Name",
  "effective_date": "YYYY-MM-DD",
  "expiry_date": "YYYY-MM-DD",
  "currency": "GBP",
  "payment_terms_days": 30,
  "notes": "Pricing terms",
  "confidence": 0.95,
  "line_items": [
    {{
      "item_code": "ITEM-1",
      "description": "Description",
      "contracted_unit_price": 50.0,
      "unit_of_measure": "EA",
      "min_quantity": 0,
      "tier_discount_pct": 0,
      "source_page_or_row": "Page 1",
      "confidence": 0.95
    }}
  ]
}}

For GOODS_RECEIVED_NOTE:
{{
  "grn_number": "GRN-101",
  "po_reference": "PO-9999",
  "received_date": "YYYY-MM-DD",
  "supplier_name": "Supplier Name",
  "confidence": 0.95,
  "line_items": [
    {{
      "item_code": "ITEM-1",
      "description": "Description",
      "quantity_received": 100.0,
      "source_page_or_row": "Page 1",
      "confidence": 0.95
    }}
  ]
}}

DOCUMENT CONTENT:
\"\"\"
{document_text}
\"\"\"
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            text_out = response.text.strip()
            # Clean markdown codeblocks if returned
            if text_out.startswith("```json"):
                text_out = text_out[7:]
            if text_out.startswith("```"):
                text_out = text_out[3:]
            if text_out.endswith("```"):
                text_out = text_out[:-3]
            
            data = json.loads(text_out.strip())
            return data
        except Exception as e:
            err_str = str(e)
            if "403" in err_str or "PERMISSION_DENIED" in err_str or "billing" in err_str.lower():
                self._billing_disabled = True
                print(f"Gemini API billing/permission error — falling back to local heuristic parser: {e}")
            else:
                print(f"Gemini API generation error: {e}")
            return None

gemini_extractor = GeminiExtractor()

