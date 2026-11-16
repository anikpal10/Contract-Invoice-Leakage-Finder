import pandas as pd
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models.finding import Finding, ReviewStatus
from backend.app.models.extracted_entities import Invoice, Contract, PurchaseOrder

class PandasProcessor:
    """
    Pandas data processing engine for aggregating, analyzing,
    and comparing contract and invoice transactions.
    """

    def build_comparison_dataframe(self, findings: List[Finding]) -> pd.DataFrame:
        """
        Builds a structured comparison DataFrame between contracts and invoices.
        """
        records = []
        for f in findings:
            records.append({
                "finding_id": f.id,
                "case_id": f.case_id,
                "category": f.finding_category,
                "supplier_name": f.supplier_name,
                "invoice_reference": f.invoice_reference,
                "product_name": f.item_description or f.item_code or "Unknown Item",
                "item_code": f.item_code or "N/A",
                "contract_unit_price": float(f.expected_amount) if f.expected_amount else 0.0,
                "invoice_unit_price": float(f.invoiced_amount) if f.invoiced_amount else 0.0,
                "cost_difference": float(f.potential_difference) if f.potential_difference else 0.0,
                "currency": f.currency,
                "severity": f.severity,
                "review_status": f.review_status,
                "explanation": f.calculation_explanation,
                "rule_version": f.rule_version,
                "created_at": f.created_at
            })

        if not records:
            return pd.DataFrame(columns=[
                "finding_id", "case_id", "category", "supplier_name",
                "invoice_reference", "product_name", "item_code",
                "contract_unit_price", "invoice_unit_price", "cost_difference",
                "currency", "severity", "review_status", "explanation", "rule_version", "created_at"
            ])

        return pd.DataFrame(records)

    def compute_dashboard_analytics(
        self,
        invoices: List[Invoice],
        findings: List[Finding]
    ) -> Dict[str, Any]:
        """
        Uses pandas to aggregate key audit metrics across invoices and findings.
        """
        df_findings = self.build_comparison_dataframe(findings)

        total_invoices = len(invoices)
        total_discrepancies = len(findings)
        
        if df_findings.empty:
            return {
                "total_invoices_analyzed": total_invoices,
                "total_discrepancies": 0,
                "total_potential_leakage": 0.00,
                "confirmed_leakage": 0.00,
                "category_breakdown": {},
                "severity_breakdown": {},
                "top_leakage_suppliers": []
            }

        # Mathematical aggregations via pandas
        total_potential_leakage = float(df_findings["cost_difference"].sum())
        
        confirmed_mask = df_findings["review_status"] == ReviewStatus.CONFIRMED.value
        confirmed_leakage = float(df_findings.loc[confirmed_mask, "cost_difference"].sum())

        # Category and Severity distributions
        cat_counts = df_findings["category"].value_counts().to_dict()
        cat_amounts = df_findings.groupby("category")["cost_difference"].sum().to_dict()

        category_breakdown = {
            cat: {
                "count": int(cat_counts.get(cat, 0)),
                "total_amount": round(float(cat_amounts.get(cat, 0.0)), 2)
            }
            for cat in cat_counts
        }

        severity_counts = df_findings["severity"].value_counts().to_dict()

        # Top 5 suppliers by leakage amount
        supplier_summary = (
            df_findings.groupby("supplier_name")["cost_difference"]
            .agg(["count", "sum"])
            .sort_values(by="sum", ascending=False)
            .head(5)
            .reset_index()
        )
        
        top_suppliers = [
            {
                "supplier_name": row["supplier_name"],
                "discrepancies_count": int(row["count"]),
                "leakage_amount": round(float(row["sum"]), 2)
            }
            for _, row in supplier_summary.iterrows()
        ]

        return {
            "total_invoices_analyzed": total_invoices,
            "total_discrepancies": total_discrepancies,
            "total_potential_leakage": round(total_potential_leakage, 2),
            "confirmed_leakage": round(confirmed_leakage, 2),
            "category_breakdown": category_breakdown,
            "severity_breakdown": {k: int(v) for k, v in severity_counts.items()},
            "top_leakage_suppliers": top_suppliers
        }

pandas_processor = PandasProcessor()

