"""
Rule-Based Intent Classifier for AP Auditor Chatbot.
Fast, deterministic keyword and regex classification with entity extraction.
"""

import re
from typing import Any, Dict, Tuple

INVOICE_REGEX = re.compile(r"\b(INV-\d+)\b", re.IGNORECASE)


def classify_intent(user_message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Classifies user message into one of:
      - APPROVE_INVOICE
      - REJECT_INVOICE
      - EXPLAIN_INVOICE
      - SHOW_FLAGGED
      - SHOW_STATS
      - CHECK_STATUS
      - GENERAL
    Returns (intent_name, entities_dict)
    """
    msg = user_message.strip()
    msg_lower = msg.lower()
    entities: Dict[str, Any] = {}

    # 1. Extract invoice ID if referenced
    inv_match = INVOICE_REGEX.search(msg)
    if inv_match:
        entities["invoice_id"] = inv_match.group(1).upper()

    # 2. Check for action on specific invoice
    if "invoice_id" in entities:
        if re.search(r"\b(approve|accepted?|clear(ed)?|sign[- ]?off|pass(ed)?)\b", msg_lower):
            return "APPROVE_INVOICE", entities
        if re.search(r"\b(reject(ed)?|den(y|ied)|block(ed)?|decline(d)?|fail(ed)?)\b", msg_lower):
            return "REJECT_INVOICE", entities
        if re.search(r"\b(why|explain|reason|details?|what happened|inspect|tell me about|info)\b", msg_lower) or len(msg.split()) <= 3:
            return "EXPLAIN_INVOICE", entities

    # 3. Check for flagged / exceptions queue
    if re.search(r"\b(flagged|exceptions?|needs?[ -]review|pending|review queue|unresolved)\b", msg_lower):
        return "SHOW_FLAGGED", entities

    # 4. Check for statistical summaries & counts
    if re.search(r"\b(summary|summarize|stats?|statistics?|metrics?|overview|kpis?|how many|breakdown)\b", msg_lower):
        return "SHOW_STATS", entities

    # 5. Check for system processing status
    if re.search(r"\b(check(ing)? invoices?|process(ing)?( the)? file|run( a)? check|audit status|system status|health)\b", msg_lower):
        return "CHECK_STATUS", entities

    # 6. Fallback to GENERAL
    return "GENERAL", entities
