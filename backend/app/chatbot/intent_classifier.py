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

# --- TIER 1: Exact / Canonical Command Matchers ---
# Matches standard, direct operational commands.
TIER1_PATTERNS = [
    # Direct approve command: e.g. "approve INV-1002"
    (re.compile(r"^\s*(?:approve|pass|accept)\s+(inv-\d+)\s*$", re.IGNORECASE), "APPROVE_INVOICE"),
    # Direct reject command: e.g. "reject INV-1002"
    (re.compile(r"^\s*(?:reject|deny|block)\s+(inv-\d+)\s*$", re.IGNORECASE), "REJECT_INVOICE"),
    # Direct explain command: e.g. "why was INV-1002 flagged", "explain INV-1002"
    (re.compile(r"^\s*(?:why\s+(?:was\s+)?|explain\s+|details\s+(?:for\s+)?|inspect\s+)(inv-\d+)(?:\s+flagged)?\s*$", re.IGNORECASE), "EXPLAIN_INVOICE"),
    # Direct flagged queue command: e.g. "show flagged", "flagged invoices", "review queue"
    (re.compile(r"^\s*(?:show\s+)?(?:flagged(?:\s+invoices?)?|exceptions?|review\s+queue|unresolved)\s*$", re.IGNORECASE), "SHOW_FLAGGED"),
    # Direct stats command: e.g. "show stats", "summary", "kpis", "metrics"
    (re.compile(r"^\s*(?:show\s+)?(?:stats?|statistics|summary|metrics?|kpis?|overview)\s*$", re.IGNORECASE), "SHOW_STATS"),
    # Direct system status command: e.g. "check status", "system status", "health"
    (re.compile(r"^\s*(?:check\s+status|system\s+status|audit\s+status|health)\s*$", re.IGNORECASE), "CHECK_STATUS"),
    # Direct export report command: e.g. "export report", "download report", "give me a report"
    (re.compile(r"^\s*(?:(?:export|download|generate|give\s+me\s+(?:a\s+)?|get)\s+)?report\s*$", re.IGNORECASE), "EXPORT_REPORT"),
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
    Tier 2 LLM classifier for natural conversational language.
    Calls Azure OpenAI (or OpenAI) using a strict JSON system prompt.
    If no key is configured or call fails, gracefully returns GENERAL.
    """
    # 1. Check if mock test provider is set
    global _tier2_test_provider
    if _tier2_test_provider is not None:
        mock_output = _tier2_test_provider(user_message)
        if mock_output is not None:
            try:
                parsed = json.loads(mock_output)
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

    # 2. Check OpenAI API configuration
    from .openai_client import get_openai_client, get_llm_model_name

    client = get_openai_client()
    model_name = get_llm_model_name()

    # If no LLM credentials are configured or placeholder, return graceful GENERAL
    if client is None:
        inv_match = INVOICE_REGEX.search(user_message)
        entities: Dict[str, Any] = {
            "tier": 2,
            "llm_handled": False,
            "fallback_reason": "No valid OpenAI API key configured.",
        }
        if inv_match:
            entities["invoice_id"] = inv_match.group(1).upper()
        return "GENERAL", entities

    system_prompt = (
        "Classify this user message into exactly one of: "
        "CHECK_STATUS, SHOW_FLAGGED, EXPLAIN_INVOICE, APPROVE_INVOICE, "
        "REJECT_INVOICE, SHOW_STATS, EXPORT_REPORT, GENERAL. "
        "Also extract any invoice_id mentioned (format INV-####). "
        "Respond in strict JSON: {\"intent\": string, \"invoice_id\": string|null}"
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            max_tokens=80,
            response_format={"type": "json_object"},
        )
        raw_content = response.choices[0].message.content or "{}"

        parsed = json.loads(raw_content)
        intent = parsed.get("intent", "GENERAL").strip().upper()
        if intent not in VALID_INTENTS:
            intent = "GENERAL"

        invoice_id = parsed.get("invoice_id")
        entities = {"tier": 2, "llm_handled": True}
        if invoice_id and isinstance(invoice_id, str) and invoice_id.strip():
            entities["invoice_id"] = invoice_id.strip().upper()
        else:
            inv_match = INVOICE_REGEX.search(user_message)
            if inv_match:
                entities["invoice_id"] = inv_match.group(1).upper()

        return intent, entities

    except Exception as e:
        logger.warning(f"Tier 2 OpenAI classification failed: {e}")
        inv_match = INVOICE_REGEX.search(user_message)
        entities = {"tier": 2, "llm_handled": False, "error": str(e)}
        if inv_match:
            entities["invoice_id"] = inv_match.group(1).upper()
        return "GENERAL", entities


def classify_intent(user_message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Main intent classification entrypoint.
    Executes TIER 1 first; if no exact match, falls through to TIER 2.
    """
    tier1_res = classify_tier1(user_message)
    if tier1_res is not None:
        return tier1_res

    return classify_tier2(user_message)
