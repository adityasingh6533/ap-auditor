"""
Audit API Router for AP Auditor.
Provides endpoints to inspect immutable audit trail logs.
"""

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Query

from ..db.database import get_connection, init_db

router = APIRouter(prefix="/api", tags=["Audit"])


@router.get("/audit-logs")
def get_audit_logs(
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum number of audit records to return (default: 50)")] = 50,
    invoice_id: Annotated[Optional[str], Query(description="Optional filter by specific invoice_id")] = None,
) -> List[Dict[str, Any]]:
    """
    Returns audit_log entries, newest first, with optional limit and invoice_id filter.
    """
    init_db()
    conn = get_connection()
    try:
        query = """
            SELECT log_id, invoice_id, action, performed_by, reason, timestamp
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
