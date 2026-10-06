"""
Audit Logger and Result Persistence for AP Auditor.
Provides functions to write invoice evaluation results and audit log decisions
into the SQLite database.
"""

from datetime import datetime, timezone
import sqlite3
from typing import Any, Dict, List, Optional
from ..db.database import get_connection, init_db
from ..db.models import compute_audit_hash


def _extract_invoice_fields(result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes a rules engine result dictionary into database column values.
    """
    invoice_id = str(result_dict.get("invoice_id", "")).strip()
    vendor_name = str(result_dict.get("vendor_name", "")).strip()
    
    amount = result_dict.get("amount")
    if amount is not None:
        try:
            amount = float(str(amount).replace(",", "").strip())
        except (ValueError, TypeError):
            amount = None

    category = str(result_dict.get("category", "")).strip()
    status = str(result_dict.get("status", "")).strip()
    
    confidence_score = result_dict.get("confidence_score")
    if confidence_score is not None:
        try:
            confidence_score = float(confidence_score)
        except (ValueError, TypeError):
            confidence_score = None

    # Handle triggered_checks (can be list of dicts, list of strings, or string)
    raw_checks = result_dict.get("triggered_checks", [])
    matched_ref = result_dict.get("matched_reference")

    if isinstance(raw_checks, list):
        check_names = []
        for item in raw_checks:
            if isinstance(item, dict):
                c_type = item.get("check_type")
                if c_type:
                    check_names.append(str(c_type))
                # Auto-extract matched reference if not provided
                if not matched_ref and "evidence" in item:
                    ev = item["evidence"]
                    if "matched_invoice_id" in ev:
                        matched_ref = ev["matched_invoice_id"]
                    elif "on_file_bank_account" in ev:
                        matched_ref = f"on-file:{ev['on_file_bank_account']}"
                    elif "po_number" in ev:
                        matched_ref = ev["po_number"]
            elif item:
                check_names.append(str(item))
        triggered_checks_str = ", ".join(check_names)
    elif raw_checks:
        triggered_checks_str = str(raw_checks)
    else:
        triggered_checks_str = ""

    reason_text = str(result_dict.get("reason_text") or result_dict.get("reason", "")).strip()
    processed_at = result_dict.get("processed_at") or datetime.now(timezone.utc).isoformat()

    return {
        "invoice_id": invoice_id,
        "vendor_name": vendor_name,
        "amount": amount,
        "category": category,
        "status": status,
        "confidence_score": confidence_score,
        "triggered_checks": triggered_checks_str,
        "reason_text": reason_text,
        "matched_reference": str(matched_ref) if matched_ref is not None else None,
        "processed_at": processed_at,
    }


def save_invoice_result(
    result_dict: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """
    Writes or updates a row in the 'invoices' table from the rules engine's output.
    """
    fields = _extract_invoice_fields(result_dict)
    query = """
    INSERT INTO invoices (
        invoice_id, vendor_name, amount, category, status,
        confidence_score, triggered_checks, reason_text, matched_reference, processed_at
    ) VALUES (
        :invoice_id, :vendor_name, :amount, :category, :status,
        :confidence_score, :triggered_checks, :reason_text, :matched_reference, :processed_at
    )
    ON CONFLICT(invoice_id) DO UPDATE SET
        vendor_name = excluded.vendor_name,
        amount = excluded.amount,
        category = excluded.category,
        status = excluded.status,
        confidence_score = excluded.confidence_score,
        triggered_checks = excluded.triggered_checks,
        reason_text = excluded.reason_text,
        matched_reference = excluded.matched_reference,
        processed_at = excluded.processed_at;
    """

    should_close = False
    if conn is None:
        init_db()
        conn = get_connection()
        should_close = True

    try:
        with conn:
            conn.execute(query, fields)
    finally:
        if should_close:
            conn.close()


def log_decision(
    invoice_id: str,
    action: str,
    performed_by: str,
    reason: Optional[str] = None,
    timestamp: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """
    Writes a row to the 'audit_log' table with cryptographic SHA-256 integrity hash.
    Returns the created log_id.
    """
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    clean_inv_id = str(invoice_id).strip()
    clean_action = str(action).strip()
    clean_performed_by = str(performed_by).strip()
    clean_reason = reason or ""
    integrity_hash = compute_audit_hash(clean_inv_id, clean_action, clean_performed_by, clean_reason, ts)

    query = """
    INSERT INTO audit_log (invoice_id, action, performed_by, reason, timestamp, integrity_hash)
    VALUES (?, ?, ?, ?, ?, ?);
    """
    params = (clean_inv_id, clean_action, clean_performed_by, clean_reason, ts, integrity_hash)

    should_close = False
    if conn is None:
        init_db()
        conn = get_connection()
        should_close = True

    try:
        with conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid
    finally:
        if should_close:
            conn.close()


def save_invoice_results_batch(
    results: List[Dict[str, Any]],
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """
    Saves multiple invoice results in a single transaction for high performance.
    """
    if not results:
        return

    query = """
    INSERT INTO invoices (
        invoice_id, vendor_name, amount, category, status,
        confidence_score, triggered_checks, reason_text, matched_reference, processed_at
    ) VALUES (
        :invoice_id, :vendor_name, :amount, :category, :status,
        :confidence_score, :triggered_checks, :reason_text, :matched_reference, :processed_at
    )
    ON CONFLICT(invoice_id) DO UPDATE SET
        vendor_name = excluded.vendor_name,
        amount = excluded.amount,
        category = excluded.category,
        status = excluded.status,
        confidence_score = excluded.confidence_score,
        triggered_checks = excluded.triggered_checks,
        reason_text = excluded.reason_text,
        matched_reference = excluded.matched_reference,
        processed_at = excluded.processed_at;
    """

    records = [_extract_invoice_fields(r) for r in results]

    should_close = False
    if conn is None:
        init_db()
        conn = get_connection()
        should_close = True

    try:
        with conn:
            chunk_size = 5000
            for i in range(0, len(records), chunk_size):
                conn.executemany(query, records[i:i + chunk_size])
    finally:
        if should_close:
            conn.close()


def log_decisions_batch(
    decisions: List[Dict[str, Any]],
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """
    Writes multiple audit log entries in a single transaction with cryptographic integrity hashes.
    Each item in decisions should have: invoice_id, action, performed_by, and optional reason, timestamp.
    """
    if not decisions:
        return

    query = """
    INSERT INTO audit_log (invoice_id, action, performed_by, reason, timestamp, integrity_hash)
    VALUES (?, ?, ?, ?, ?, ?);
    """
    now_ts = datetime.now(timezone.utc).isoformat()
    params_list = []
    for d in decisions:
        inv = str(d.get("invoice_id", "")).strip()
        act = str(d.get("action", "")).strip()
        perf = str(d.get("performed_by", "SYSTEM")).strip()
        rsn = d.get("reason", "") or ""
        t_stamp = d.get("timestamp") or now_ts
        h = compute_audit_hash(inv, act, perf, rsn, t_stamp)
        params_list.append((inv, act, perf, rsn, t_stamp, h))

    should_close = False
    if conn is None:
        init_db()
        conn = get_connection()
        should_close = True

    try:
        with conn:
            chunk_size = 5000
            for i in range(0, len(params_list), chunk_size):
                conn.executemany(query, params_list[i:i + chunk_size])
    finally:
        if should_close:
            conn.close()
