"""
Statistics API Router for AP Auditor.
Aggregates compliance metrics, processing volumes, and failure rule breakdowns.
"""

from collections import Counter
from typing import Any, Dict
from fastapi import APIRouter

from ..db.database import get_connection, init_db

router = APIRouter(prefix="/api", tags=["Stats"])


@router.get("/stats")
def get_stats() -> Dict[str, Any]:
    """
    Returns high-level statistics across all audited invoices:
    - total_processed
    - auto_pass_count
    - flagged_count
    - needs_review_count
    - breakdown: frequency count of each triggered check type
    """
    init_db()
    conn = get_connection()
    try:
        # Get total counts and status breakdown
        status_cur = conn.execute("""
            SELECT status, COUNT(*) as cnt
            FROM invoices
            GROUP BY status
        """)
        status_counts = {row["status"]: row["cnt"] for row in status_cur.fetchall()}

        auto_pass_count = status_counts.get("AUTO_PASS", 0)
        flagged_count = status_counts.get("FLAGGED_AUTO", 0)
        needs_review_count = status_counts.get("NEEDS_HUMAN_REVIEW", 0)
        total_processed = sum(status_counts.values())

        # Count occurrences of each value in triggered_checks
        checks_cur = conn.execute("""
            SELECT triggered_checks
            FROM invoices
            WHERE triggered_checks IS NOT NULL AND triggered_checks != ''
        """)
        breakdown_counter: Counter[str] = Counter()
        for row in checks_cur.fetchall():
            raw_checks = row["triggered_checks"]
            if raw_checks:
                for check in raw_checks.split(","):
                    check_name = check.strip()
                    if check_name:
                        breakdown_counter[check_name] += 1

        return {
            "total_processed": total_processed,
            "auto_pass_count": auto_pass_count,
            "flagged_count": flagged_count,
            "needs_review_count": needs_review_count,
            "breakdown": dict(breakdown_counter),
        }
    finally:
        conn.close()
