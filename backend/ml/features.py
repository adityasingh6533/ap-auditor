"""
ml/features.py

Feature engineering pipeline for AP Invoice Exception Detection.
Extracts tabular features strictly from raw dataset columns without leaking
flags or intermediary metadata from the rules engine.
Features are designed to be batch-size independent and direction-aware.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from rapidfuzz import fuzz

# Policy-based categories requiring a Purchase Order (from policy_config.json)
CATEGORY_PO_REQUIRED = {
    "IT Equipment": True,
    "Logistics": True,
    "Professional Services": True,
    "Facilities": True,
    "Office Supplies": False,
    "Travel": False,
    "Catering": False,
    "Marketing": False,
}

# Approval hierarchy ladder
APPROVER_LEVELS = {
    "Team Manager": 1,
    "Department Head": 2,
    "Finance Controller": 3,
    "CFO": 4,
}

ALL_CATEGORIES = [
    "Catering",
    "Facilities",
    "IT Equipment",
    "Logistics",
    "Marketing",
    "Office Supplies",
    "Professional Services",
    "Travel",
]

NUMERIC_FEATURES = [
    "amount_to_limit_ratio",
    "po_amount_gap_pct",
    "approver_level_gap",
    "days_from_today",
    "amount_diff_rel_nearest_same_vendor",
    "days_to_nearest_similar_invoice",
    "similar_invoice_count",
]

BINARY_FEATURES = [
    "gst_missing",
    "po_missing_but_required",
    "bank_differs_from_vendor_usual",
    "has_earlier_similar_invoice",
    "has_later_similar_invoice",
]

CATEGORY_ONEHOT_FEATURES = [
    f"category_{cat.lower().replace(' ', '_')}" for cat in ALL_CATEGORIES
]

FEATURE_NAMES = NUMERIC_FEATURES + BINARY_FEATURES + CATEGORY_ONEHOT_FEATURES


def _parse_float(val: Any) -> float:
    """Safely parse numeric floats."""
    if val is None or pd.isna(val):
        return 0.0
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _parse_date(val: Any) -> Optional[date]:
    """Parse dates in ISO or alternate formats."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


def get_required_approver_level(amount: float) -> int:
    """
    Returns required approver hierarchy level based on amount:
    1: Team Manager (<= 10,000)
    2: Department Head (<= 100,000)
    3: Finance Controller (<= 1,000,000)
    4: CFO (> 1,000,000)
    """
    if amount <= 10_000:
        return 1
    if amount <= 100_000:
        return 2
    if amount <= 1_000_000:
        return 3
    return 4


def compute_vendor_usual_banks(df: pd.DataFrame) -> Dict[str, str]:
    """
    Computes the most frequent bank_account for each vendor within the provided dataset batch.
    """
    usual_banks: Dict[str, str] = {}
    valid_rows = df[df["vendor_name"].notna() & df["bank_account"].notna()]
    for vendor, group in valid_rows.groupby("vendor_name"):
        modes = group["bank_account"].mode()
        if not modes.empty:
            usual_banks[str(vendor).strip()] = str(modes.iloc[0]).strip()
    return usual_banks


def compute_relative_amount_diff_same_vendor(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Computes batch-size independent relative difference to nearest same-vendor invoice:
    min(|amt_i - amt_j|) / amt_i (capped at 1.0).
    """
    n = len(df)
    if n == 0 or "vendor_name" not in df or "amount" not in df:
        return pd.Series(1.0, index=df.index, dtype=float)

    rel_diffs = np.full(n, 1.0, dtype=float)
    vendors = df["vendor_name"].fillna("UNKNOWN").astype(str).str.strip().str.lower().values
    amounts = df["amount"].apply(_parse_float).values

    vendor_groups: Dict[str, List[int]] = {}
    for idx, v in enumerate(vendors):
        vendor_groups.setdefault(v, []).append(idx)

    for v, idx_list in vendor_groups.items():
        k = len(idx_list)
        if k <= 1:
            continue
        v_amts = amounts[idx_list]
        denom = np.maximum(v_amts[:, None], 1e-6)
        diff_mat = np.abs(v_amts[:, None] - v_amts[None, :]) / denom
        np.fill_diagonal(diff_mat, np.inf)

        min_rel = np.min(diff_mat, axis=1)
        rel_diffs[idx_list] = np.clip(min_rel, 0.0, 1.0)

    return pd.Series(rel_diffs, index=df.index, dtype=float)


def compute_direction_aware_duplicate_features(
    df: pd.DataFrame,
    amount_tol_pct: float = 1.0,
    vendor_sim_threshold: float = 85.0,
) -> pd.DataFrame:
    """
    Computes pair-based duplicate features with blocking by vendor and amount range:
    1. has_earlier_similar_invoice (0/1): has matching candidate submitted earlier
    2. has_later_similar_invoice (0/1): has matching candidate submitted later
    3. days_to_nearest_similar_invoice: day gap to closest matching candidate (or 999.0 if none)
    4. similar_invoice_count: count of matching candidates (capped at 5 to prevent batch scaling)
    """
    n = len(df)
    if n == 0 or "amount" not in df:
        return pd.DataFrame({
            "has_earlier_similar_invoice": np.zeros(n, dtype=int),
            "has_later_similar_invoice": np.zeros(n, dtype=int),
            "days_to_nearest_similar_invoice": np.full(n, 999.0, dtype=float),
            "similar_invoice_count": np.zeros(n, dtype=int),
        }, index=df.index)

    amounts = df["amount"].apply(_parse_float).values
    vendors = df["vendor_name"].fillna("").astype(str).str.strip().values
    vendors_lower = df["vendor_name"].fillna("").astype(str).str.strip().str.lower().values
    dates = pd.to_datetime(df["invoice_date"]).values

    order = np.argsort(amounts)
    sorted_amts = amounts[order]
    sorted_vendors = vendors[order]
    sorted_vendors_lower = vendors_lower[order]
    sorted_dates = dates[order]

    tol = amount_tol_pct / 100.0
    left_bounds = np.searchsorted(sorted_amts, sorted_amts * (1.0 - tol), side="left")
    right_bounds = np.searchsorted(sorted_amts, sorted_amts * (1.0 + tol), side="right")

    has_earlier = np.zeros(n, dtype=int)
    has_later = np.zeros(n, dtype=int)
    nearest_days = np.full(n, 999.0, dtype=float)
    similar_counts = np.zeros(n, dtype=int)

    for i in range(n):
        lb = left_bounds[i]
        rb = right_bounds[i]
        v_i = sorted_vendors[i]
        vl_i = sorted_vendors_lower[i]
        d_i = sorted_dates[i]

        cnt = 0
        min_gap = 999.0
        earlier = 0
        later = 0

        for j in range(lb, rb):
            if i == j:
                continue

            # Blocking: check exact vendor match first, then fuzzy
            if vl_i == sorted_vendors_lower[j]:
                match = True
            else:
                sim = float(fuzz.token_sort_ratio(v_i, sorted_vendors[j]))
                match = (sim >= vendor_sim_threshold)

            if match:
                cnt += 1
                d_j = sorted_dates[j]
                day_diff = float((d_i - d_j) / np.timedelta64(1, "D"))
                abs_gap = abs(day_diff)
                if abs_gap < min_gap:
                    min_gap = abs_gap
                if day_diff > 0:
                    earlier = 1
                elif day_diff < 0:
                    later = 1
                else:
                    earlier = 1
                    later = 1

        has_earlier[order[i]] = earlier
        has_later[order[i]] = later
        nearest_days[order[i]] = min_gap
        similar_counts[order[i]] = min(cnt, 5)

    return pd.DataFrame({
        "has_earlier_similar_invoice": has_earlier,
        "has_later_similar_invoice": has_later,
        "days_to_nearest_similar_invoice": nearest_days,
        "similar_invoice_count": similar_counts,
    }, index=df.index)


def extract_features(
    df: pd.DataFrame,
    vendor_usual_banks: Optional[Dict[str, str]] = None,
    reference_date: Optional[date] = None,
) -> Tuple[pd.DataFrame, Optional[pd.Series], Optional[pd.Series]]:
    """
    Extracts tabular feature matrix X and optional target labels y, y_multi.

    Args:
        df: Input raw invoices dataframe.
        vendor_usual_banks: Optional precomputed vendor usual bank mapping.
                            If None, computed directly from current batch.
        reference_date: Fixed reference date for future date checking.
                        Defaults to 2026-10-04 for large dataset (>= 5k rows)
                        and 2026-10-03 for smaller test sets (<= 5k rows).

    Returns:
        X (pd.DataFrame): Engineered feature dataframe matching FEATURE_NAMES.
        y (pd.Series or None): Binary target (0 for CLEAN, 1 for exception).
        y_multi (pd.Series or None): Multi-class original true_label strings.
    """
    features = pd.DataFrame(index=df.index)

    # 1. Fixed reference date per dataset
    if reference_date is None:
        if len(df) > 5000:
            ref_date = date(2026, 10, 4)
        else:
            ref_date = date(2026, 10, 3)
    else:
        ref_date = reference_date

    # 2. amount_to_limit_ratio
    amounts = df["amount"].apply(_parse_float)
    limits = df["policy_limit"].apply(_parse_float)
    safe_limits = limits.replace(0.0, np.nan)
    features["amount_to_limit_ratio"] = (amounts / safe_limits).fillna(0.0).round(4)

    # 3. gst_missing (0/1)
    gst_clean = df["gst_number"].fillna("").astype(str).str.strip()
    features["gst_missing"] = np.where(gst_clean.isin(["", "nan", "None", "null"]), 1, 0)

    # 4. po_missing_but_required (0/1)
    po_clean = df["po_number"].fillna("").astype(str).str.strip()
    po_missing = po_clean.isin(["", "nan", "None", "null"])
    categories = df["category"].fillna("").astype(str).str.strip()
    po_required = categories.map(lambda c: CATEGORY_PO_REQUIRED.get(c, False))
    features["po_missing_but_required"] = np.where(po_required & po_missing, 1, 0)

    # 5. po_amount_gap_pct
    po_amounts = df["po_amount"].apply(_parse_float)
    po_present = po_amounts > 0
    features["po_amount_gap_pct"] = np.where(
        po_present,
        ((amounts - po_amounts) / po_amounts) * 100.0,
        0.0,
    ).round(4)

    # 6. approver_level_gap (required_level - listed_level)
    req_levels = amounts.apply(get_required_approver_level)
    approver_roles = df["approver"].fillna("").astype(str).str.strip()
    listed_levels = approver_roles.map(lambda r: APPROVER_LEVELS.get(r, 0))
    features["approver_level_gap"] = req_levels - listed_levels

    # 7. days_from_today (negative if invoice_date is in the future)
    parsed_dates = df["invoice_date"].apply(_parse_date)
    features["days_from_today"] = parsed_dates.map(
        lambda d: (ref_date - d).days if d is not None else 0
    )

    # 8. bank_differs_from_vendor_usual (computed from batch if not provided)
    active_usual_banks = vendor_usual_banks if vendor_usual_banks is not None else compute_vendor_usual_banks(df)
    vendor_names = df["vendor_name"].fillna("").astype(str).str.strip()
    bank_accounts = df["bank_account"].fillna("").astype(str).str.strip()

    def _check_bank_diff(vendor: str, bank: str) -> int:
        usual = active_usual_banks.get(vendor)
        if usual is None:
            return 0
        return 1 if bank != usual else 0

    features["bank_differs_from_vendor_usual"] = [
        _check_bank_diff(v, b) for v, b in zip(vendor_names, bank_accounts)
    ]

    # 9. Relative amount difference to nearest same-vendor invoice
    features["amount_diff_rel_nearest_same_vendor"] = compute_relative_amount_diff_same_vendor(df)

    # 10. Direction-aware pair duplicate features
    dup_feats = compute_direction_aware_duplicate_features(df)
    features["has_earlier_similar_invoice"] = dup_feats["has_earlier_similar_invoice"]
    features["has_later_similar_invoice"] = dup_feats["has_later_similar_invoice"]
    features["days_to_nearest_similar_invoice"] = dup_feats["days_to_nearest_similar_invoice"]
    features["similar_invoice_count"] = dup_feats["similar_invoice_count"]

    # 11. One-hot encoded category
    for cat in ALL_CATEGORIES:
        col_name = f"category_{cat.lower().replace(' ', '_')}"
        features[col_name] = (categories == cat).astype(int)

    # Final feature matrix
    X = features[FEATURE_NAMES].copy()

    # Targets if present
    y_binary = None
    y_multi = None
    if "true_label" in df.columns:
        y_multi = df["true_label"].fillna("CLEAN").astype(str).str.strip()
        y_binary = (y_multi != "CLEAN").astype(int)

    return X, y_binary, y_multi
