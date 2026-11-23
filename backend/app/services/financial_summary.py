from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Any

from backend.app.models.finding import FindingCategory

REVIEW_REQUIRED_CURRENCY = "REVIEW_REQUIRED"

_SYMBOLS = {
    "INR": "₹",
    "GBP": "£",
    "USD": "$",
    "EUR": "€",
    "CAD": "C$",
    "AUD": "A$",
    "JPY": "¥",
}

# Eligible leakage categories (gross overcharge candidates)
OVERCHARGE_CATEGORIES = {
    FindingCategory.CONTRACT_PRICE_MISMATCH.value,
    FindingCategory.PO_PRICE_MISMATCH.value,
    FindingCategory.QUANTITY_OVER_PO.value,
    FindingCategory.QUANTITY_OVER_GRN.value,
    FindingCategory.DUPLICATE_INVOICE.value,
    FindingCategory.MISSING_CREDIT_OR_AMENDMENT.value,
}

# Eligible undercharge categories (potential under-billing candidates)
UNDERCHARGE_CATEGORIES = {
    FindingCategory.POTENTIAL_UNDERCHARGE.value,
}


def normalize_currency(code: Optional[str]) -> str:
    c = (code or "").strip().upper()
    return c if c else REVIEW_REQUIRED_CURRENCY


def get_currency_symbol(code: Optional[str]) -> str:
    curr = normalize_currency(code)
    return _SYMBOLS.get(curr, f"{curr} ")


def is_eligible_overcharge(finding: Any) -> bool:
    return (
        getattr(finding, "finding_category", None) in OVERCHARGE_CATEGORIES
        and Decimal(getattr(finding, "potential_difference", Decimal("0.00"))) > Decimal("0.00")
    )


def is_eligible_undercharge(finding: Any) -> bool:
    """
    A potential undercharge is a price variance where the invoice billed BELOW the
    agreed contract/PO rate. The stored potential_difference is negative, so we
    report the absolute magnitude as the undercharge exposure.
    """
    return (
        getattr(finding, "finding_category", None) in UNDERCHARGE_CATEGORIES
        and Decimal(getattr(finding, "potential_difference", Decimal("0.00"))) < Decimal("0.00")
    )


def undercharge_amount(finding: Any) -> Decimal:
    """Return the positive magnitude of an undercharge finding's variance."""
    return abs(Decimal(getattr(finding, "potential_difference", Decimal("0.00")) or Decimal("0.00")))


def deduplicate_findings_for_financial_summary(findings: Iterable[Any]) -> List[Any]:
    """
    Prevents double-counting between aggregate invoice-level findings and
    child line-level findings for the same invoice (Requirement 5).

    If an invoice has both INCORRECT_INVOICE_TOTAL (header aggregate) and
    child INCORRECT_LINE_TOTAL findings, we exclude the aggregate header finding
    to prevent summing both parent and children together.
    """
    by_invoice: Dict[str, List[Any]] = {}
    non_invoice_findings: List[Any] = []

    for f in findings:
        inv_ref = getattr(f, "invoice_reference", None)
        if inv_ref:
            by_invoice.setdefault(inv_ref, []).append(f)
        else:
            non_invoice_findings.append(f)

    result: List[Any] = list(non_invoice_findings)

    for inv_ref, inv_findings in by_invoice.items():
        header_math_findings = [
            f for f in inv_findings
            if getattr(f, "finding_category", None) == FindingCategory.INCORRECT_INVOICE_TOTAL.value
        ]
        line_math_findings = [
            f for f in inv_findings
            if getattr(f, "finding_category", None) == FindingCategory.INCORRECT_LINE_TOTAL.value
        ]

        if header_math_findings and line_math_findings:
            # Exclude the aggregate header finding so child lines aren't double counted
            filtered_inv_findings = [f for f in inv_findings if f not in header_math_findings]
            result.extend(filtered_inv_findings)
        else:
            result.extend(inv_findings)

    return result


def aggregate_amounts_by_currency(
    records: Iterable[Any],
    amount_attr: str,
    *,
    status_attr: Optional[str] = None,
    status_equals: Optional[str] = None,
    predicate: Optional[Any] = None,
    currency_attr: str = "currency",
) -> Dict[str, Decimal]:
    # Deduplicate aggregate and child findings if records are findings
    clean_records = deduplicate_findings_for_financial_summary(records)

    out: Dict[str, Decimal] = {}
    for rec in clean_records:
        if status_attr and status_equals is not None and getattr(rec, status_attr) != status_equals:
            continue
        if predicate and not predicate(rec):
            continue

        c = normalize_currency(getattr(rec, currency_attr, None))
        amount = Decimal(getattr(rec, amount_attr, Decimal("0.00")) or Decimal("0.00"))
        out[c] = out.get(c, Decimal("0.00")) + amount
    return out


def single_currency_total(breakdown: Dict[str, Decimal]) -> Optional[Decimal]:
    if len(breakdown) == 1:
        return next(iter(breakdown.values()))
    return None


def currency_status(breakdown: Dict[str, Decimal]) -> str:
    if not breakdown:
        return "NONE"
    if len(breakdown) == 1:
        only = next(iter(breakdown.keys()))
        return "REVIEW_REQUIRED" if only == REVIEW_REQUIRED_CURRENCY else "SINGLE"
    return "MIXED"


def net_variance_by_currency(
    overcharge_breakdown: Dict[str, Decimal],
    undercharge_breakdown: Dict[str, Decimal],
) -> Dict[str, Decimal]:
    """
    Net variance = gross overcharges - potential undercharges, computed per currency.

    Overcharges and undercharges are kept as separate gross metrics; the net
    variance is a derived figure that must never replace the gross metrics.
    """
    currencies = set(overcharge_breakdown) | set(undercharge_breakdown)
    out: Dict[str, Decimal] = {}
    for c in currencies:
        over = Decimal(overcharge_breakdown.get(c, Decimal("0.00")) or Decimal("0.00"))
        under = Decimal(undercharge_breakdown.get(c, Decimal("0.00")) or Decimal("0.00"))
        out[c] = over - under
    return out

