"""
Limit and Authority Checker for AP invoices.
Checks policy spend limits, approval authority ladder, PO amount tolerances, and future invoice dates.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from .config_loader import (
    get_category_policy,
    get_approval_ladder,
    get_po_tolerance_percent,
)


def _parse_float(val: Any) -> Optional[float]:
    """Helper to safely parse numeric amount."""
    if val is None or pd.isna(val):
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_date(val: Any) -> Optional[date]:
    """Helper to parse dates in multiple formats."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        dt = pd.to_datetime(s)
        return dt.date()
    except Exception:
        return None


def check_policy_limit(
    row: Dict[str, Any] | pd.Series,
    category_policy: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Flags if amount > policy_limit for its category (or row policy_limit).
    Confidence is scaled between 0.65 and 0.95 depending on how significantly the limit was exceeded.
    """
    amount = _parse_float(row.get("amount"))
    if amount is None:
        return None

    category = str(row.get("category", "")).strip()
    policy_limit = _parse_float(row.get("policy_limit"))

    if policy_limit is None:
        policies = category_policy if category_policy is not None else get_category_policy()
        cat_info = policies.get(category)
        if cat_info:
            policy_limit = cat_info.get("limit")

    if policy_limit is None or policy_limit <= 0:
        return None

    if amount > policy_limit:
        overage = amount - policy_limit
        pct_over = (overage / policy_limit) * 100
        
        # Scaling confidence: minor breach (e.g. 5%) ~0.70, major breach (e.g. >50%) ~0.95
        confidence = min(0.95, 0.70 + 0.25 * min(1.0, overage / (policy_limit * 0.5)))

        return {
            "check_type": "OVER_LIMIT",
            "severity": "HIGH" if pct_over > 20 else "MEDIUM",
            "base_confidence": round(confidence, 3),
            "evidence": {
                "amount": amount,
                "policy_limit": policy_limit,
                "category": category,
                "overage": overage,
                "overage_percent": round(pct_over, 2),
            },
            "reason": (
                f"Invoice amount ₹{amount:,.2f} exceeds '{category}' policy limit "
                f"of ₹{policy_limit:,.2f} by ₹{overage:,.2f} ({pct_over:.1f}% over limit)."
            ),
        }
    return None


def _get_required_approver_role(amount: float, ladder: Optional[Dict[str, float]] = None) -> Tuple[str, float]:
    """Determines minimum required approver role and authority limit for an amount."""
    active_ladder = ladder if ladder is not None else get_approval_ladder()
    for role, limit in sorted(active_ladder.items(), key=lambda x: x[1]):
        if amount <= limit:
            return role, limit
    return "CFO", float("inf")


def check_approval_authority(
    row: Dict[str, Any] | pd.Series,
    approval_ladder: Optional[Dict[str, float]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Flags if listed approver's authority (per ladder) is lower than what the amount requires:
    - Team Manager: up to 10,000
    - Department Head: up to 100,000
    - Finance Controller: up to 1,000,000
    - CFO: above that
    """
    amount = _parse_float(row.get("amount"))
    if amount is None or amount <= 0:
        return None

    approver = str(row.get("approver", "")).strip()
    if not approver or approver.lower() in ("nan", "none", "null"):
        return {
            "check_type": "APPROVAL_MISMATCH",
            "severity": "HIGH",
            "base_confidence": 0.90,
            "evidence": {"approver": None, "amount": amount},
            "reason": f"No designated approver found for invoice amount ₹{amount:,.2f}."
        }

    ladder = approval_ladder if approval_ladder is not None else get_approval_ladder()

    # Match approver role from ladder
    approver_limit: Optional[float] = None
    approver_matched_role = approver

    # Look for matching role name in ladder
    for role, limit in ladder.items():
        if role.lower() in approver.lower() or approver.lower() in role.lower():
            approver_limit = limit
            approver_matched_role = role
            break

    # If role not found directly, check if standard mapped names exist
    if approver_limit is None:
        approver_limit = ladder.get(approver)

    # If still not recognized, treat as Team Manager level (minimum) or flag
    if approver_limit is None:
        approver_limit = ladder.get("Team Manager", 10000.0)

    if amount > approver_limit:
        required_role, required_limit = _get_required_approver_role(amount, ladder=ladder)
        gap_ratio = amount / approver_limit if approver_limit > 0 else 2.0
        confidence = min(0.92, 0.70 + 0.15 * min(1.0, (gap_ratio - 1.0) / 2.0))

        return {
            "check_type": "APPROVAL_MISMATCH",
            "severity": "HIGH" if amount > 100000 else "MEDIUM",
            "base_confidence": round(confidence, 3),
            "evidence": {
                "approver": approver,
                "approver_role": approver_matched_role,
                "approver_limit": approver_limit,
                "amount": amount,
                "required_role": required_role,
                "required_limit": required_limit,
            },
            "reason": (
                f"Approver '{approver}' authority limit (₹{approver_limit:,.0f}) is insufficient "
                f"for invoice amount ₹{amount:,.2f}; requires authority of '{required_role}'."
            ),
        }
    return None


def check_po_amount_mismatch(
    row: Dict[str, Any] | pd.Series,
    tolerance_fraction: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    If po_amount exists, flags if amount exceeds po_amount by more than tolerance.
    """
    amount = _parse_float(row.get("amount"))
    po_amount = _parse_float(row.get("po_amount"))

    if amount is None or po_amount is None or po_amount <= 0:
        return None

    tol = tolerance_fraction if tolerance_fraction is not None else get_po_tolerance_percent()
    allowed_threshold = po_amount * (1.0 + tol)

    if amount > allowed_threshold:
        overage = amount - po_amount
        pct_over = (overage / po_amount) * 100.0
        
        # Scale confidence based on excess percentage
        confidence = min(0.92, 0.65 + 0.20 * min(1.0, (pct_over - (tol * 100.0)) / 25.0))

        return {
            "check_type": "PO_AMOUNT_MISMATCH",
            "severity": "HIGH" if pct_over > 15.0 else "MEDIUM",
            "base_confidence": round(confidence, 3),
            "evidence": {
                "amount": amount,
                "po_amount": po_amount,
                "allowed_threshold": allowed_threshold,
                "overage": overage,
                "overage_percent": round(pct_over, 2),
                "tolerance_percent": tol * 100.0,
            },
            "reason": (
                f"Invoice amount ₹{amount:,.2f} exceeds PO amount ₹{po_amount:,.2f} by "
                f"{pct_over:.1f}% (exceeds allowable tolerance of {tol*100.0:.1f}%)."
            ),
        }
    return None


def check_future_date(row: Dict[str, Any] | pd.Series, reference_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """
    Flags if invoice_date is after today (or reference_date).
    """
    invoice_date = _parse_date(row.get("invoice_date"))
    if invoice_date is None:
        return None

    ref_date = reference_date or date.today()

    if invoice_date > ref_date:
        days_ahead = (invoice_date - ref_date).days
        return {
            "check_type": "FUTURE_DATE",
            "severity": "HIGH",
            "base_confidence": 0.95,
            "evidence": {
                "invoice_date": invoice_date.isoformat(),
                "reference_date": ref_date.isoformat(),
                "days_ahead": days_ahead,
            },
            "reason": (
                f"Invoice date {invoice_date.isoformat()} is post-dated in the future "
                f"({days_ahead} day(s) after today {ref_date.isoformat()})."
            ),
        }
    return None


def check_all_limits(row: Dict[str, Any] | pd.Series, reference_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """Runs all limit, approval, PO mismatch, and date checks on a single row."""
    flags: List[Dict[str, Any]] = []

    p_flag = check_policy_limit(row)
    if p_flag:
        flags.append(p_flag)

    a_flag = check_approval_authority(row)
    if a_flag:
        flags.append(a_flag)

    po_flag = check_po_amount_mismatch(row)
    if po_flag:
        flags.append(po_flag)

    d_flag = check_future_date(row, reference_date)
    if d_flag:
        flags.append(d_flag)

    return flags
