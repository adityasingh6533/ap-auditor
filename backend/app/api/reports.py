"""
API router for exporting AP Audit reports.
Supports PDF and CSV downloads.
"""

from fastapi import APIRouter, Query, Response
from ..reports.report_generator import generate_exception_report

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/export")
def export_report(format: str = Query("pdf", description="Report format: 'pdf' or 'csv'")):
    """
    Generates and downloads the executive exception report summarizing:
    - Overall processed, clean, flagged, and review counts
    - All flagged invoices grouped by violation issue type
    """
    content, media_type = generate_exception_report(format=format)
    ext = "pdf" if "pdf" in media_type else "csv"
    filename = f"ap_exception_report.{ext}"

    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content

    return Response(
        content=content_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
