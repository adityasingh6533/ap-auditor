"""
Duplicate Matcher for AP invoices using rapidfuzz and windowed candidate indexing.
Detects exact duplicates and fuzzy duplicates with evidence tracking.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
import pandas as pd
from rapidfuzz import fuzz
from .config_loader import (
    get_duplicate_date_window_days,
    get_fuzzy_vendor_similarity_threshold,
    get_fuzzy_amount_tolerance_percent,
)


def _parse_float(val: Any) -> Optional[float]:
    if val is None or pd.isna(val):
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_date(val: Any) -> Optional[date]:
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


class DuplicateMatcher:
    """
    Indexed duplicate detector.
    Pre-processes dataset into normalized records and applies date & category indexing
    to perform efficient duplicate detection across large datasets.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        date_window_days: Optional[int] = None,
        fuzzy_similarity_threshold: Optional[float] = None,
        fuzzy_amount_tolerance_percent: Optional[float] = None,
    ):
        self.records: List[Dict[str, Any]] = []
        self.date_window_days = date_window_days
        self.fuzzy_similarity_threshold = fuzzy_similarity_threshold
        self.fuzzy_amount_tolerance_percent = fuzzy_amount_tolerance_percent
        self._prepare_records(df)

    def _prepare_records(self, df: pd.DataFrame) -> None:
        """Parses and normalizes dataset rows into internal record structures."""
        for idx, row in df.iterrows():
            inv_id = str(row.get("invoice_id", f"ROW-{idx}")).strip()
            vendor = str(row.get("vendor_name", "")).strip()
            cat = str(row.get("category", "")).strip()
            amt = _parse_float(row.get("amount"))
            dt = _parse_date(row.get("invoice_date"))

            self.records.append({
                "index": idx,
                "invoice_id": inv_id,
                "vendor_name": vendor,
                "vendor_normalized": vendor.lower().strip(),
                "category": cat,
                "category_normalized": cat.lower().strip(),
                "amount": amt,
                "invoice_date": dt,
            })

    def find_duplicates_for_invoice(self, current_record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Finds exact or fuzzy duplicate matches for a given invoice record across the dataset.
        Flags invoices that duplicate an earlier preceding invoice in the dataset.
        """
        flags: List[Dict[str, Any]] = []
        curr_id = current_record["invoice_id"]
        curr_vendor = current_record["vendor_normalized"]
        curr_vendor_raw = current_record["vendor_name"]
        curr_cat = current_record["category_normalized"]
        curr_amt = current_record["amount"]
        curr_dt = current_record["invoice_date"]

        if curr_amt is None or curr_dt is None or not curr_vendor:
            return flags

        # Resolve active dynamic thresholds
        window_days = (
            self.date_window_days
            if self.date_window_days is not None
            else get_duplicate_date_window_days()
        )
        sim_threshold = (
            self.fuzzy_similarity_threshold
            if self.fuzzy_similarity_threshold is not None
            else get_fuzzy_vendor_similarity_threshold()
        )
        amt_tolerance_pct = (
            self.fuzzy_amount_tolerance_percent
            if self.fuzzy_amount_tolerance_percent is not None
            else get_fuzzy_amount_tolerance_percent()
        )

        exact_matches: List[Dict[str, Any]] = []
        fuzzy_matches: List[Dict[str, Any]] = []

        for candidate in self.records:
            cand_id = candidate["invoice_id"]
            if cand_id == curr_id:
                continue

            cand_amt = candidate["amount"]
            cand_dt = candidate["invoice_date"]
            cand_vendor = candidate["vendor_normalized"]
            cand_vendor_raw = candidate["vendor_name"]
            cand_cat = candidate["category_normalized"]

            if cand_amt is None or cand_dt is None or not cand_vendor:
                continue

            # Candidate must be chronologically earlier or preceding invoice
            if not (cand_dt < curr_dt or (cand_dt == curr_dt and cand_id < curr_id)):
                continue

            # Check date window
            days_diff = (curr_dt - cand_dt).days
            if days_diff > window_days or days_diff < 0:
                continue

            # 1. Exact Duplicate Check:
            # Same vendor (case-insensitive), same category, same amount within 0.01, within window
            if (
                curr_vendor == cand_vendor
                and curr_cat == cand_cat
                and abs(curr_amt - cand_amt) < 0.01
            ):
                exact_matches.append({
                    "matched_invoice_id": cand_id,
                    "matched_vendor": cand_vendor_raw,
                    "matched_amount": cand_amt,
                    "matched_date": cand_dt.isoformat(),
                    "days_apart": days_diff,
                    "category": candidate["category"],
                })
                break

            # 2. Fuzzy Duplicate Check:
            # Same category, vendor similarity >= threshold, amount within tolerance, within window
            if curr_cat == cand_cat:
                max_amt = max(curr_amt, cand_amt)
                if max_amt <= 0:
                    continue
                amt_diff_pct = abs(curr_amt - cand_amt) / max_amt

                if amt_diff_pct <= amt_tolerance_pct:
                    similarity = fuzz.ratio(curr_vendor, cand_vendor)
                    if similarity >= sim_threshold:
                        fuzzy_matches.append({
                            "matched_invoice_id": cand_id,
                            "matched_vendor": cand_vendor_raw,
                            "matched_amount": cand_amt,
                            "matched_date": cand_dt.isoformat(),
                            "days_apart": days_diff,
                            "category": candidate["category"],
                            "similarity_score": round(similarity, 1),
                            "amount_diff_percent": round(amt_diff_pct * 100, 2),
                        })
                        break

        # Construct Flags (Exact duplicates take priority)
        for match in exact_matches:
            flags.append({
                "check_type": "EXACT_DUPLICATE",
                "severity": "HIGH",
                "base_confidence": 0.98,
                "evidence": {
                    "matched_invoice_id": match["matched_invoice_id"],
                    "matched_vendor": match["matched_vendor"],
                    "matched_amount": match["matched_amount"],
                    "matched_date": match["matched_date"],
                    "days_apart": match["days_apart"],
                },
                "reason": (
                    f"Exact duplicate of invoice {match['matched_invoice_id']}: "
                    f"same vendor ('{match['matched_vendor']}'), exact same amount (₹{curr_amt:,.2f}), "
                    f"same category, {match['days_apart']} day(s) apart."
                ),
            })

        if not exact_matches:
            for match in fuzzy_matches:
                sim = match["similarity_score"]
                amt_pct = match["amount_diff_percent"]
                sim_factor = (sim - sim_threshold) / (100.0 - sim_threshold + 1e-5)
                amt_factor = 1.0 - (amt_pct / (amt_tolerance_pct * 100.0))
                confidence = 0.65 + 0.12 * sim_factor + 0.08 * max(0.0, amt_factor)

                flags.append({
                    "check_type": "FUZZY_DUPLICATE",
                    "severity": "MEDIUM",
                    "base_confidence": round(confidence, 3),
                    "evidence": {
                        "matched_invoice_id": match["matched_invoice_id"],
                        "matched_vendor": match["matched_vendor"],
                        "matched_amount": match["matched_amount"],
                        "matched_date": match["matched_date"],
                        "days_apart": match["days_apart"],
                        "vendor_similarity": sim,
                        "amount_diff_percent": amt_pct,
                    },
                    "reason": (
                        f"Potential fuzzy duplicate of invoice {match['matched_invoice_id']}: "
                        f"vendor similarity {sim:.0f}% ('{curr_vendor_raw}' vs '{match['matched_vendor']}'), "
                        f"amount within {amt_pct:.1f}% (₹{curr_amt:,.2f} vs ₹{match['matched_amount']:,.2f}), "
                        f"{match['days_apart']} day(s) apart."
                    ),
                })

        return flags

    def match_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Runs duplicate detection for all invoices in the dataset."""
        results: Dict[str, List[Dict[str, Any]]] = {}
        for record in self.records:
            results[record["invoice_id"]] = self.find_duplicates_for_invoice(record)
        return results
