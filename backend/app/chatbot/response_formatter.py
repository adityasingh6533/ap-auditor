"""
Response Formatter for AP Auditor Chatbot.
Generates human-friendly, deterministic conversational replies from raw query data.
"""

from typing import Any, Dict, Optional


def format_response(intent: str, status: str, data: Optional[Dict[str, Any]]) -> str:
    """
    Transforms raw handler dictionary data into a clean, professional assistant reply.
    """
    if status == "MISSING_ENTITY":
        return data.get("error", "Please specify an invoice ID (e.g. INV-3918).") if data else "Missing invoice ID."

    if status == "NOT_FOUND":
        return data.get("error", "The requested invoice could not be found.") if data else "Record not found."

    if status == "ERROR":
        return f"An error occurred while processing your request: {data.get('error', 'Unknown error') if data else 'Unknown error'}"

    if not data:
        return "I processed your request, but no additional data was returned."

    # 1. Statistical Summary / System Status
    if intent in ("SHOW_STATS", "CHECK_STATUS"):
        stats = data.get("stats", {})
        total = stats.get("total_processed", 0)
        auto_pass = stats.get("auto_pass_count", 0)
        flagged = stats.get("flagged_count", 0)
        needs_review = stats.get("needs_review_count", 0)
        breakdown = stats.get("breakdown", {})

        top_rules = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)[:4]
        rules_summary = ", ".join(f"{count} {rule}" for rule, count in top_rules) if top_rules else "None"

        reply = (
            f"I checked {total:,} invoices. {auto_pass:,} passed automatically, "
            f"{flagged:,} were flagged, and {needs_review:,} need your review.\n\n"
            f"Top exceptions identified: {rules_summary}."
        )
        return reply

    # 2. Flagged Invoices Queue
    if intent == "SHOW_FLAGGED":
        exceptions = data.get("exceptions", [])
        if not exceptions:
            return "Good news! There are currently no unresolved flagged invoices or exceptions awaiting human review."

        lines = [f"I found {len(exceptions)} high-priority exception(s) awaiting your review:"]
        for exc in exceptions:
            inv_id = exc.get("invoice_id", "")
            vendor = exc.get("vendor_name", "Unknown")
            amt = exc.get("amount")
            amt_str = f"₹{amt:,.2f}" if isinstance(amt, (int, float)) else str(amt)
            status_tag = exc.get("status", "")
            reason = exc.get("reason_text", "")
            lines.append(f"• **{inv_id}** — {vendor} ({amt_str}) [{status_tag}]: {reason}")

        lines.append("\nYou can inspect any invoice by asking `why was <INV_ID> flagged` or take action with `approve <INV_ID>` / `reject <INV_ID>`.")
        return "\n".join(lines)

    # 3. Explain Specific Invoice
    if intent == "EXPLAIN_INVOICE":
        inv = data.get("invoice", {})
        inv_id = inv.get("invoice_id", "")
        vendor = inv.get("vendor_name", "Unknown Vendor")
        amt = inv.get("amount")
        amt_str = f"₹{amt:,.2f}" if isinstance(amt, (int, float)) else str(amt)
        status_val = inv.get("status", "")
        reason = inv.get("reason_text") or "Passed standard rules engine criteria."
        score = inv.get("confidence_score")
        score_str = f"{score:.1%}" if isinstance(score, (int, float)) else "N/A"
        checks = inv.get("triggered_checks") or "None"
        matched_ref = inv.get("matched_reference")

        reply = (
            f"**{inv_id}** ({vendor}, {amt_str}) is currently marked as **{status_val}**.\n\n"
            f"• **Triggered Rules**: {checks}\n"
            f"• **Reason**: {reason}\n"
            f"• **Confidence Score**: {score_str}"
        )
        if matched_ref:
            reply += f"\n• **Matched Reference**: {matched_ref}"

        return reply

    # 4. Approve Invoice
    if intent == "APPROVE_INVOICE":
        inv_id = data.get("invoice_id", "")
        log_id = data.get("log_id", "")
        return f"Got it, **{inv_id}** has been approved and logged to the immutable audit trail (Log ID #{log_id})."

    # 5. Reject Invoice
    if intent == "REJECT_INVOICE":
        inv_id = data.get("invoice_id", "")
        log_id = data.get("log_id", "")
        return f"Got it, **{inv_id}** has been rejected and logged to the immutable audit trail (Log ID #{log_id})."

    # 6. Export Report
    if intent == "EXPORT_REPORT":
        download_url = data.get("download_url", "/api/reports/export") if data else "/api/reports/export"
        return (
            "📊 **AP Audit Exception Report Ready**\n\n"
            f"You can download the full exceptions report here: [Download Report]({download_url})\n\n"
            "This report includes total processed invoices, pass/flag counts, and itemized evidence for every flagged item."
        )

    return "Your request has been handled successfully."
