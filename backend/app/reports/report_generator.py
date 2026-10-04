"""
Report Generator for Accounts Payable Compliance and Exceptions.
Generates an executive PDF report (or formatted CSV) summarizing audit metrics
and listing flagged invoices grouped by violation issue type.
"""

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..db.database import get_connection, init_db


def fetch_report_data() -> Tuple[Dict[str, int], Dict[str, List[Dict[str, Any]]]]:
    """
    Queries the database for overall metrics and grouped flagged invoices.
    Returns (summary_stats, grouped_by_issue).
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM invoices")
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    total = len(rows)
    auto_pass = sum(1 for r in rows if r.get("status") == "AUTO_PASS")
    flagged_auto = sum(1 for r in rows if r.get("status") == "FLAGGED_AUTO")
    needs_review = sum(1 for r in rows if r.get("status") == "NEEDS_HUMAN_REVIEW")

    summary_stats = {
        "total_processed": total,
        "auto_pass_count": auto_pass,
        "flagged_count": flagged_auto,
        "needs_review_count": needs_review,
        "clean_rate_percent": round((auto_pass / total * 100) if total > 0 else 0, 1),
    }

    grouped_by_issue: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:
        if row.get("status") == "AUTO_PASS":
            continue

        raw_checks = row.get("triggered_checks")
        check_types = []
        if raw_checks:
            try:
                parsed = json.loads(raw_checks) if isinstance(raw_checks, str) else raw_checks
                if isinstance(parsed, list):
                    check_types = [c.get("check_type", "UNKNOWN") for c in parsed if isinstance(c, dict)]
            except Exception:
                pass

        if not check_types:
            check_types = ["OTHER_EXCEPTION"]

        item = {
            "invoice_id": row.get("invoice_id", "N/A"),
            "vendor": row.get("vendor_name", "N/A"),
            "amount": row.get("amount", 0.0),
            "status": row.get("status", "FLAGGED"),
            "confidence": row.get("confidence_score", 0.0),
            "reason": row.get("reason_text", ""),
            "matched_reference": row.get("matched_reference") or "-",
        }

        # Place into primary group
        primary_issue = check_types[0]
        if primary_issue not in grouped_by_issue:
            grouped_by_issue[primary_issue] = []
        grouped_by_issue[primary_issue].append(item)

    return summary_stats, grouped_by_issue


def generate_exception_report_pdf(output_path: Optional[str | Path] = None) -> bytes:
    """
    Generates a PDF exception report using ReportLab.
    Returns bytes or writes to output_path.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        KeepTogether,
        HRFlowable,
    )

    summary_stats, grouped = fetch_report_data()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0078D4"),
        alignment=0,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#555555"),
    )
    h2_style = ParagraphStyle(
        "Heading2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1A1A1A"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#222222"),
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    elements = []

    # Title & Metadata
    elements.append(Paragraph("AP AUDITOR — EXCEPTION & COMPLIANCE REPORT", title_style))
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"Generated: {now_str} | Confidential AP Audit Trail", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0078D4"), spaceAfter=12))

    # Summary Stats Table
    summary_data = [
        ["Total Processed", "Auto-Passed (Clean)", "Flagged (Auto)", "Needs Human Review", "Clean Rate"],
        [
            f"{summary_stats['total_processed']:,}",
            f"{summary_stats['auto_pass_count']:,}",
            f"{summary_stats['flagged_count']:,}",
            f"{summary_stats['needs_review_count']:,}",
            f"{summary_stats['clean_rate_percent']}%",
        ],
    ]
    summary_table = Table(summary_data, colWidths=[108] * 5)
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F4F8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#004B87")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
        ])
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 16))

    # Exception Breakdown Summary
    elements.append(Paragraph("EXCEPTIONS BY ISSUE TYPE", h2_style))
    breakdown_headers = ["Issue Type Category", "Flagged Count", "Priority Severity"]
    breakdown_rows = [breakdown_headers]
    for issue_type, items in sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True):
        sev = "HIGH" if "DUPLICATE" in issue_type or "BANK" in issue_type or "GST" in issue_type else "MEDIUM"
        breakdown_rows.append([issue_type, f"{len(items):,} invoices", sev])

    breakdown_table = Table(breakdown_rows, colWidths=[240, 150, 150])
    breakdown_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A1A24")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E1E4E8")),
        ])
    )
    elements.append(breakdown_table)
    elements.append(Spacer(1, 16))

    # Detailed Grouped Invoices (top 15 per group to keep PDF concise)
    elements.append(Paragraph("DETAILED AUDIT LOGS (GROUPED BY ISSUE TYPE)", h2_style))

    for issue_type, items in sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True):
        group_elements = []
        group_elements.append(Spacer(1, 6))
        group_elements.append(Paragraph(f"• {issue_type} ({len(items)} items)", body_bold))

        item_headers = ["Invoice ID", "Vendor", "Amount (₹)", "Matched Ref", "Audit Reason & Evidence"]
        table_rows = [item_headers]

        # Show up to 25 items per group
        sample_items = items[:25]
        for itm in sample_items:
            amt_str = f"₹{itm['amount']:,.2f}" if itm['amount'] else "-"
            # Truncate reason for table fit
            reason_snip = (itm["reason"][:110] + "...") if len(itm["reason"]) > 110 else itm["reason"]
            table_rows.append([
                itm["invoice_id"],
                (itm["vendor"][:20] + "..") if len(itm["vendor"]) > 20 else itm["vendor"],
                amt_str,
                itm["matched_reference"][:16],
                Paragraph(reason_snip, body_style),
            ])

        if len(items) > 25:
            table_rows.append(["...", f"... and {len(items)-25} more items", "", "", ""])

        grp_table = Table(table_rows, colWidths=[65, 95, 80, 75, 225])
        grp_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EFF5")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E1E4E8")),
            ])
        )
        group_elements.append(grp_table)
        elements.append(KeepTogether(group_elements))

    doc.build(elements)
    pdf_bytes = buf.getvalue()

    if output_path:
        Path(output_path).write_bytes(pdf_bytes)

    return pdf_bytes


def generate_exception_report_csv(output_path: Optional[str | Path] = None) -> str:
    """
    Generates a structured, well-formatted CSV report summarizing audit metrics
    and listing all flagged invoices grouped by violation issue type.
    """
    summary_stats, grouped = fetch_report_data()
    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Header Metadata
    writer.writerow(["=== AP AUDITOR EXCEPTION & COMPLIANCE AUDIT REPORT ==="])
    writer.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])

    # 2. Executive Summary
    writer.writerow(["--- EXECUTIVE SUMMARY ---"])
    writer.writerow(["Total Processed", summary_stats["total_processed"]])
    writer.writerow(["Auto-Passed (Clean)", summary_stats["auto_pass_count"]])
    writer.writerow(["Flagged (High Confidence)", summary_stats["flagged_count"]])
    writer.writerow(["Needs Human Review", summary_stats["needs_review_count"]])
    writer.writerow(["Clean Rate (%)", f"{summary_stats['clean_rate_percent']}%"])
    writer.writerow([])

    # 3. Grouped Exceptions
    writer.writerow(["--- FLAGGED INVOICES GROUPED BY ISSUE TYPE ---"])
    writer.writerow(["Issue Type", "Invoice ID", "Vendor", "Amount (INR)", "Status", "Confidence", "Matched Reference", "Audit Reason"])

    for issue_type, items in sorted(grouped.items()):
        for item in items:
            writer.writerow([
                issue_type,
                item["invoice_id"],
                item["vendor"],
                f"{item['amount']:.2f}" if item['amount'] else "",
                item["status"],
                item["confidence"],
                item["matched_reference"],
                item["reason"],
            ])

    csv_text = output.getvalue()
    if output_path:
        Path(output_path).write_text(csv_text, encoding="utf-8")

    return csv_text


def generate_exception_report(format: str = "pdf", output_path: Optional[str | Path] = None) -> Tuple[bytes | str, str]:
    """
    Primary interface for generating the exception report.
    Returns (content, media_type).
    """
    if format.lower() == "pdf":
        try:
            pdf_bytes = generate_exception_report_pdf(output_path=output_path)
            return pdf_bytes, "application/pdf"
        except Exception as e:
            # Fallback to CSV if PDF generation has issues
            csv_str = generate_exception_report_csv(output_path=output_path)
            return csv_str, "text/csv"
    else:
        csv_str = generate_exception_report_csv(output_path=output_path)
        return csv_str, "text/csv"
