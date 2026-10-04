"""
Query Router for AP Auditor Chatbot.
Directly dispatches classified user intents to internal Python modules without network calls.
"""

from typing import Any, Dict, Optional, Tuple
from ..api.exceptions import ReviewDecisionRequest, get_exceptions, submit_review_decision
from ..api.stats import get_stats
from ..db.database import get_connection, init_db


def handle_intent(intent: str, entities: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Executes internal handlers based on intent and extracted entities.
    Returns (status_label, raw_data_dict)
    """
    invoice_id = entities.get("invoice_id")

    if intent in ("SHOW_STATS", "CHECK_STATUS"):
        stats_data = get_stats()
        return "SUCCESS", {"stats": stats_data}

    elif intent == "SHOW_FLAGGED":
        # Fetch top 5 exceptions awaiting review
        exceptions_data = get_exceptions(limit=5)
        return "SUCCESS", {"exceptions": exceptions_data}

    elif intent == "EXPLAIN_INVOICE":
        if not invoice_id:
            return "MISSING_ENTITY", {"error": "Please specify an invoice ID (e.g. INV-3918)."}

        init_db()
        conn = get_connection()
        try:
            cur = conn.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,))
            inv_row = cur.fetchone()
            if not inv_row:
                return "NOT_FOUND", {"error": f"Invoice '{invoice_id}' was not found in the database."}

            log_cur = conn.execute(
                "SELECT log_id, action, performed_by, reason, timestamp FROM audit_log WHERE invoice_id = ? ORDER BY log_id DESC LIMIT 3",
                (invoice_id,),
            )
            audit_records = [dict(r) for r in log_cur.fetchall()]

            return "SUCCESS", {
                "invoice": dict(inv_row),
                "audit_trail": audit_records,
            }
        finally:
            conn.close()

    elif intent == "APPROVE_INVOICE":
        if not invoice_id:
            return "MISSING_ENTITY", {"error": "Please specify which invoice to approve (e.g. 'approve INV-3918')."}

        try:
            result = submit_review_decision(
                invoice_id=invoice_id,
                payload=ReviewDecisionRequest(
                    decision="approve",
                    reviewer="AI Copilot",
                    reason="Approved via AP conversational interface",
                ),
            )
            return "SUCCESS", result
        except Exception as e:
            return "ERROR", {"error": str(e)}

    elif intent == "REJECT_INVOICE":
        if not invoice_id:
            return "MISSING_ENTITY", {"error": "Please specify which invoice to reject (e.g. 'reject INV-3918')."}

        try:
            result = submit_review_decision(
                invoice_id=invoice_id,
                payload=ReviewDecisionRequest(
                    decision="reject",
                    reviewer="AI Copilot",
                    reason="Rejected via AP conversational interface",
                ),
            )
            return "SUCCESS", result
        except Exception as e:
            return "ERROR", {"error": str(e)}

    elif intent == "EXPORT_REPORT":
        return "SUCCESS", {
            "download_url": "/api/reports/export",
            "message": "AP Audit Exception Report is available for download.",
        }

    # For GENERAL or unhandled intents, return None so fallback can handle
    return "FALLBACK", None
