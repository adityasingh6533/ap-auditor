"""
Invoices API Router for AP Auditor.
Handles CSV invoice uploads, rules engine processing, and querying invoices with filters.
"""

from pathlib import Path
import io
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
import pandas as pd

from ..audit.logger import log_decisions_batch, save_invoice_results_batch
from ..db.database import get_connection, init_db
from ..rules_engine.engine import RulesEngine

router = APIRouter(prefix="/api", tags=["Invoices"])


@router.post("/upload")
async def upload_invoices(
    file: UploadFile = File(...),
    replace: bool = Query(True, description="Replace current active dataset with this uploaded file"),
) -> Dict[str, Any]:
    """
    Accepts a CSV file upload, runs it through the rules engine,
    and updates the database with the results.
    When replace=True (default), purges previous invoices and logs so
    the dashboard reflects exactly the newly uploaded dataset.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV file: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

    # Execute Rules Engine across all uploaded rows
    try:
        engine = RulesEngine()
        results = engine.process_dataframe(df, save_to_db=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing invoices through rules engine: {str(e)}")

    # Ensure DB tables are initialized
    init_db()
    conn = get_connection()
    try:
        if replace:
            with conn:
                conn.execute("DELETE FROM invoices;")
                conn.execute("DELETE FROM audit_log;")

        # Save invoice evaluation records
        save_invoice_results_batch(results, conn=conn)

        # Log system decisions
        decisions = [
            {
                "invoice_id": r.get("invoice_id", ""),
                "action": r.get("status", ""),
                "performed_by": "SYSTEM",
                "reason": r.get("reason", "") or r.get("reason_text", ""),
            }
            for r in results
        ]
        log_decisions_batch(decisions, conn=conn)
    finally:
        conn.close()

    # Aggregate summary counts
    auto_pass_count = sum(1 for r in results if r.get("status") == "AUTO_PASS")
    flagged_count = sum(1 for r in results if r.get("status") == "FLAGGED_AUTO")
    needs_review_count = sum(1 for r in results if r.get("status") == "NEEDS_HUMAN_REVIEW")

    return {
        "total": len(results),
        "auto_pass_count": auto_pass_count,
        "flagged_count": flagged_count,
        "needs_review_count": needs_review_count,
        "dataset_active": True,
    }


@router.post("/dataset/reset")
def reset_dataset() -> Dict[str, Any]:
    """
    Resets the database to 0 invoices and clears all audit logs for a clean state.
    """
    init_db()
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM invoices;")
            conn.execute("DELETE FROM audit_log;")
    finally:
        conn.close()

    return {
        "message": "Dataset reset to 0 records. Clean workspace ready for upload.",
        "total": 0,
        "auto_pass_count": 0,
        "flagged_count": 0,
        "needs_review_count": 0,
    }


@router.post("/dataset/clear")
def clear_dataset() -> Dict[str, Any]:
    """
    Alias to reset dataset to 0 records.
    """
    return reset_dataset()


@router.post("/dataset/load-demo")
def load_demo_dataset() -> Dict[str, Any]:
    """
    Loads the canonical benchmark demo dataset (data/invoices_dataset.csv) with 3,000 records.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = base_dir / "data" / "invoices_dataset.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Default dataset invoices_dataset.csv not found.")

    try:
        df = pd.read_csv(csv_path)
        engine = RulesEngine()
        results = engine.process_dataframe(df, save_to_db=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process default dataset: {str(e)}")

    init_db()
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM invoices;")
            conn.execute("DELETE FROM audit_log;")

        save_invoice_results_batch(results, conn=conn)
        decisions = [
            {
                "invoice_id": r.get("invoice_id", ""),
                "action": r.get("status", ""),
                "performed_by": "SYSTEM",
                "reason": r.get("reason", "") or r.get("reason_text", ""),
            }
            for r in results
        ]
        log_decisions_batch(decisions, conn=conn)
    finally:
        conn.close()

    auto_pass_count = sum(1 for r in results if r.get("status") == "AUTO_PASS")
    flagged_count = sum(1 for r in results if r.get("status") == "FLAGGED_AUTO")
    needs_review_count = sum(1 for r in results if r.get("status") == "NEEDS_HUMAN_REVIEW")

    return {
        "message": "Demo dataset loaded (3,000 invoices).",
        "total": len(results),
        "auto_pass_count": auto_pass_count,
        "flagged_count": flagged_count,
        "needs_review_count": needs_review_count,
    }


@router.get("/invoices")
def get_invoices(
    status: Annotated[Optional[str], Query(description="Filter by status: AUTO_PASS, FLAGGED_AUTO, NEEDS_HUMAN_REVIEW, etc.")] = None,
    category: Annotated[Optional[str], Query(description="Filter by category (e.g. IT Equipment, Facilities)")] = None,
    vendor_name: Annotated[Optional[str], Query(description="Filter by vendor name (fuzzy/substring match)")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum number of rows to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Offset for pagination")] = 0,
) -> List[Dict[str, Any]]:
    """
    Returns invoices from the SQLite database as JSON with optional filtering and pagination.
    """
    init_db()
    conn = get_connection()
    try:
        query = """
            SELECT invoice_id, vendor_name, amount, category, status,
                   confidence_score, triggered_checks, reason_text, matched_reference, processed_at
            FROM invoices
            WHERE 1=1
        """
        params: List[Any] = []

        if status:
            query += " AND UPPER(status) = UPPER(?)"
            params.append(status.strip())

        if category:
            query += " AND UPPER(category) = UPPER(?)"
            params.append(category.strip())

        if vendor_name:
            query += " AND vendor_name LIKE ?"
            params.append(f"%{vendor_name.strip()}%")

        query += " ORDER BY processed_at DESC, invoice_id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/invoices/{invoice_id}")
def get_invoice_by_id(invoice_id: str) -> Dict[str, Any]:
    """
    Returns full invoice details for a specific invoice ID.
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id.strip(),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found.")
        return dict(row)
    finally:
        conn.close()

