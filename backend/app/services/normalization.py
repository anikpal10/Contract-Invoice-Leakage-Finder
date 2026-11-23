import re
import string
from typing import Optional
from decimal import Decimal
from rapidfuzz import fuzz

class NormalizationService:
    @staticmethod
    def normalize_supplier_name(name: str) -> str:
        """
        Removes legal suffixes (Ltd, Limited, LLC, Inc, PLC, Corp, UK) and punctuation.
        """
        if not name:
            return ""
        cleaned = name.upper().strip()
        # Remove common corporate suffixes
        suffixes = [
            r"\bLIMITED\b", r"\bLTD\.?\b", r"\bINC\.?\b", r"\bLLC\b",
            r"\bPLC\b", r"\bCORP\.?\b", r"\bCORPORATION\b", r"\bUK\b",
            r"\bSERVICES\b", r"\bGROUP\b", r"\bSUPPLIES\b"
        ]
        for s in suffixes:
            cleaned = re.sub(s, "", cleaned, flags=re.IGNORECASE).strip()
        # Remove punctuation
        cleaned = cleaned.translate(str.maketrans("", "", string.punctuation))
        # Collapse multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def normalize_code(code: Optional[str]) -> str:
        if not code:
            return ""
        # Remove hyphens, spaces, leading zeroes
        cleaned = re.sub(r"[\s\-_]", "", code.upper())
        return cleaned.lstrip("0")

    @staticmethod
    def normalize_description(desc: str) -> str:
        if not desc:
            return ""
        cleaned = desc.lower().strip()
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def calculate_similarity(s1: str, s2: str) -> float:
        """
        Returns similarity score between 0.0 and 1.0 using token sort ratio.
        """
        if not s1 or not s2:
            return 0.0
        return fuzz.token_sort_ratio(s1, s2) / 100.0

    @staticmethod
    def calculate_token_set_similarity(s1: str, s2: str) -> float:
        """
        Returns similarity score between 0.0 and 1.0 using token set ratio (robust to subsets).
        """
        if not s1 or not s2:
            return 0.0
        return fuzz.token_set_ratio(s1, s2) / 100.0

normalization_service = NormalizationService()

