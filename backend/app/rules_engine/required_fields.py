"""
Required fields validation for AP invoices.
Checks for missing GST number and required PO numbers based on spend category.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
from .config_loader import get_category_policy


def _is_empty_or_na(val: Any) -> bool:
    """Helper to determine if a value is missing, empty, or whitespace."""
    if val is None:
        return True
    if pd.isna(val):
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none", "null", "n/a", "na")


def check_required_fields(
    row: Dict[str, Any] | pd.Series,
    category_policy: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Validates required fields for an invoice:
    1. gst_number must be present and non-empty.
    2. po_number must be present if the category requires a PO.

    Returns a list of violation flag dictionaries.
    """
    flags: List[Dict[str, Any]] = []

    category = str(row.get("category", "")).strip()
    gst_number = row.get("gst_number")
    po_number = row.get("po_number")

    # 1. GST Number Check
    if _is_empty_or_na(gst_number):
        flags.append({
            "check_type": "MISSING_GST",
            "severity": "HIGH",
            "base_confidence": 0.95,
            "evidence": {"field": "gst_number", "value": gst_number},
            "reason": "GST number is missing or invalid on the invoice."
        })

    # 2. PO Number Check based on Category
    policies = category_policy if category_policy is not None else get_category_policy()
    category_rule = policies.get(category)
    po_required = category_rule.get("po_required", False) if category_rule else False

    if po_required and _is_empty_or_na(po_number):
        flags.append({
            "check_type": "MISSING_PO",
            "severity": "HIGH",
            "base_confidence": 0.95,
            "evidence": {
                "field": "po_number",
                "category": category,
                "po_required": True,
                "value": po_number
            },
            "reason": f"PO number is mandatory for category '{category}' but is missing."
        })

    return flags
