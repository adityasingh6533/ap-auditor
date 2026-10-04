"""
Hybrid Two-Tier Intent Classifier for AP Auditor Chatbot.

TIER 1: Fast, deterministic regex/keyword matching for common exact phrases.
        Instant and zero-cost.
TIER 2: Azure OpenAI (or OpenAI) LLM fallback for conversational/natural language.
        Extracts structured intent and invoice_id in strict JSON.
        If no API key is configured, gracefully falls back to GENERAL.
"""

import json
import logging
import os
import re
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

INVOICE_REGEX = re.compile(r"\b(INV-\d+)\b", re.IGNORECASE)

VALID_INTENTS = {
    "CHECK_STATUS",
    "SHOW_FLAGGED",
    "EXPLAIN_INVOICE",
    "APPROVE_INVOICE",
    "REJECT_INVOICE",
    "SHOW_STATS",
    "EXPORT_REPORT",
    "GENERAL",
}

# --- TIER 1: Exact / Canonical & Common Operational Patterns ---
TIER1_PATTERNS = [
    # Approve variants: "approve INV-1002", "I want to sign off on INV-1002", "sign off on INV-1002"
    (re.compile(r".*?\b(?:sign\s*off(?:\s+on)?|approve|pass|accept|clear)\s+(inv-\d+)\b.*?", re.IGNORECASE), "APPROVE_INVOICE"),
    # Reject variants: "reject INV-1002", "deny INV-1002", "block INV-1002"
    (re.compile(r".*?\b(?:reject|deny|block|disallow)\s+(inv-\d+)\b.*?", re.IGNORECASE), "REJECT_INVOICE"),
    # Explain variants: "why was INV-1002 flagged", "explain INV-1002", "details for INV-1002"
    (re.compile(r".*?\b(?:why\s+(?:was\s+)?|explain\s+|details\s+(?:for\s+)?|inspect\s+|what\s+happened\s+(?:to|with)\s+)(inv-\d+)\b.*?", re.IGNORECASE), "EXPLAIN_INVOICE"),
    # Flagged / stuck queue variants: "which invoices got stuck", "show flagged", "stuck invoices"
    (re.compile(r".*?\b(?:(?:which\s+invoices\s+(?:got\s+|are\s+)?stuck)|stuck\s+invoices?|flagged(?:\s+invoices?)?|review\s+queue|exceptions?|unresolved)\b.*?", re.IGNORECASE), "SHOW_FLAGGED"),
    # Stats / summary variants: "what's going on with the invoices today", "show stats", "summary"
    (re.compile(r".*?\b(?:what'?s\s+going\s+on\s+with\s+(?:the\s+)?invoices|stats?|statistics|summary|metrics?|kpis?|overview)\b.*?", re.IGNORECASE), "SHOW_STATS"),
    # System status / health
    (re.compile(r".*?\b(?:check\s+status|system\s+status|audit\s+status|health)\b.*?", re.IGNORECASE), "CHECK_STATUS"),
    # Export report
    (re.compile(r".*?\b(?:export|download|generate|get)\s+report\b.*?", re.IGNORECASE), "EXPORT_REPORT"),
]


def classify_tier1(user_message: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Tier 1 fast keyword and regex matching for exact, common commands.
    Returns (intent, entities) if matched, otherwise None.
    """
    msg = user_message.strip()

    for pattern, intent in TIER1_PATTERNS:
        match = pattern.match(msg)
        if match:
            entities: Dict[str, Any] = {"tier": 1}
            # Look for invoice ID inside captured groups
            for group in match.groups():
                if group and group.upper().startswith("INV-"):
                    entities["invoice_id"] = group.upper()
                    break

            if "invoice_id" not in entities:
                inv_match = INVOICE_REGEX.search(msg)
                if inv_match:
                    entities["invoice_id"] = inv_match.group(1).upper()

            return intent, entities

    return None


# Optional hook for testing Tier 2 responses without network calls
_tier2_test_provider: Optional[Callable[[str], Optional[str]]] = None


def set_tier2_test_provider(provider: Optional[Callable[[str], Optional[str]]]) -> None:
    """Sets a mock provider for testing Tier 2 LLM outputs."""
    global _tier2_test_provider
    _tier2_test_provider = provider


def classify_tier2(user_message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Tier 2 LLM classifier for natural conversational language using Google Gemini.
    Extracts structured intent and invoice_id in strict JSON.
    If no key is configured or call fails, gracefully returns GENERAL.
    """
    # 1. Check if mock test provider is set
    global _tier2_test_provider
    if _tier2_test_provider is not None:
        mock_output = _tier2_test_provider(user_message)
        if mock_output is not None:
            try:
                from .gemini_client import clean_json_markdown
                cleaned = clean_json_markdown(mock_output)
                parsed = json.loads(cleaned)
                intent = parsed.get("intent", "GENERAL").strip().upper()
                if intent not in VALID_INTENTS:
                    intent = "GENERAL"
                entities: Dict[str, Any] = {"tier": 2, "llm_handled": True}
                inv = parsed.get("invoice_id")
                if inv:
                    entities["invoice_id"] = str(inv).strip().upper()
                return intent, entities
            except Exception as e:
                logger.warning(f"Failed to parse mock Tier 2 JSON: {e}")

    # 2. Call Google Gemini (gemini-2.0-flash)
    from .llm_fallback import classify_with_gemini
    return classify_with_gemini(user_message)


def classify_intent(user_message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Main intent classification entrypoint.
    Executes TIER 1 first; if no exact match, falls through to TIER 2.
    """
    tier1_res = classify_tier1(user_message)
    if tier1_res is not None:
        return tier1_res

    return classify_tier2(user_message)
