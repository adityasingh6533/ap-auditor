"""
Audit API Router for AP Auditor.
Provides endpoints to inspect immutable audit trail logs and
verify cryptographic integrity against tampering.
"""

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Query

from ..db.database import get_connection, init_db
from ..db.models import compute_audit_hash

router = APIRouter(prefix="/api", tags=["Audit"])


@router.get("/audit-logs")
def get_audit_logs(
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum number of audit records to return (default: 50)")] = 50,
    invoice_id: Annotated[Optional[str], Query(description="Optional filter by specific invoice_id")] = None,
) -> List[Dict[str, Any]]:
    """
    Returns audit_log entries, newest first, with optional limit and invoice_id filter.
    Includes the SHA-256 cryptographic integrity hash for each record.
    """
    init_db()
    conn = get_connection()
    try:
        query = """
            SELECT log_id, invoice_id, action, performed_by, reason, timestamp, integrity_hash
            FROM audit_log
            WHERE 1=1
        """
        params: List[Any] = []

        if invoice_id:
            query += " AND invoice_id = ?"
            params.append(invoice_id.strip())

        query += " ORDER BY log_id DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/audit-logs/verify")
def verify_audit_log_integrity() -> Dict[str, Any]:
    """
    Recomputes SHA-256 cryptographic integrity hashes for all rows in the audit log
    and detects any unauthorized modifications or tampering.
    """
    init_db()
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT log_id, invoice_id, action, performed_by, reason, timestamp, integrity_hash FROM audit_log ORDER BY log_id ASC"
        )
        rows = cursor.fetchall()

        total = len(rows)
        verified_clean = 0
        tampered_records: List[Dict[str, Any]] = []

        for r in rows:
            lid = r["log_id"]
            inv_id = r["invoice_id"]
            action = r["action"]
            perf = r["performed_by"]
            reason = r["reason"] or ""
            ts = r["timestamp"]
            stored_hash = r["integrity_hash"]

            calculated_hash = compute_audit_hash(inv_id, action, perf, reason, ts)

            if stored_hash == calculated_hash:
                verified_clean += 1
            else:
                tampered_records.append({
                    "log_id": lid,
                    "invoice_id": inv_id,
                    "action": action,
                    "stored_hash": stored_hash,
                    "expected_hash": calculated_hash,
                })

        is_clean = len(tampered_records) == 0

        return {
            "status": "ALL_CLEAN" if is_clean else "TAMPERING_DETECTED",
            "total_records_checked": total,
            "verified_clean": verified_clean,
            "tampered_count": len(tampered_records),
            "tampered_records": tampered_records,
            "message": (
                "All audit log records verified clean with valid cryptographic signatures."
                if is_clean
                else f"Integrity check failed: {len(tampered_records)} record(s) show tampering."
            ),
        }
    finally:
        conn.close()
