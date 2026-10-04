"""
Exceptions API Router for AP Auditor.
Handles exception queue retrieval and human auditor approval/rejection actions.
"""

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..audit.logger import log_decision
from ..db.database import get_connection, init_db

router = APIRouter(prefix="/api", tags=["Exceptions"])


class ReviewDecisionRequest(BaseModel):
    decision: str = Field(..., description="Action to take: 'approve' or 'reject'")
    reviewer: str = Field(..., description="Identifier/name of the reviewer (e.g., 'J. Doe')")
    reason: Optional[str] = Field(None, description="Optional explanation for the review decision")


@router.get("/exceptions")
def get_exceptions(
    limit: Annotated[Optional[int], Query(ge=1, le=1000, description="Optional limit of exception records to return")] = None,
    offset: Annotated[int, Query(ge=0, description="Offset for pagination")] = 0,
) -> List[Dict[str, Any]]:
    """
    Returns only invoices where status is FLAGGED_AUTO or NEEDS_HUMAN_REVIEW,
    including reason_text, matched_reference, confidence_score, and triggered_checks.
    """
    init_db()
    conn = get_connection()
    try:
        query = """
            SELECT invoice_id, vendor_name, amount, category, status,
                   confidence_score, triggered_checks, reason_text, matched_reference, processed_at
            FROM invoices
            WHERE status IN ('FLAGGED_AUTO', 'NEEDS_HUMAN_REVIEW')
            ORDER BY
                CASE status
                    WHEN 'NEEDS_HUMAN_REVIEW' THEN 1
                    WHEN 'FLAGGED_AUTO' THEN 2
                    ELSE 3
                END,
                processed_at DESC,
                invoice_id ASC
        """
        params: List[Any] = []
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/review/{invoice_id}/decision")
def submit_review_decision(
    invoice_id: str,
    payload: ReviewDecisionRequest,
) -> Dict[str, Any]:
    """
    Updates the invoice status and calls log_decision() with action = HUMAN_APPROVED or HUMAN_REJECTED.
    """
    clean_decision = payload.decision.strip().lower()
    if clean_decision not in ("approve", "reject"):
        raise HTTPException(
            status_code=400,
            detail="Invalid decision. Must be either 'approve' or 'reject'.",
        )

    action = "HUMAN_APPROVED" if clean_decision == "approve" else "HUMAN_REJECTED"
    new_status = action

    init_db()
    conn = get_connection()
    try:
        # Check if invoice exists
        cur = conn.execute("SELECT invoice_id, status FROM invoices WHERE invoice_id = ?", (invoice_id.strip(),))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Invoice '{invoice_id}' not found.",
            )

        # Update invoice status
        conn.execute(
            "UPDATE invoices SET status = ? WHERE invoice_id = ?",
            (new_status, invoice_id.strip()),
        )
        conn.commit()

        # Log decision in audit_log
        log_id = log_decision(
            invoice_id=invoice_id.strip(),
            action=action,
            performed_by=payload.reviewer.strip(),
            reason=payload.reason or f"Human auditor marked invoice as {clean_decision}d.",
            conn=conn,
        )

        return {
            "success": True,
            "invoice_id": invoice_id.strip(),
            "status": new_status,
            "action": action,
            "performed_by": payload.reviewer.strip(),
            "log_id": log_id,
        }
    finally:
        conn.close()
