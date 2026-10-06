"""
Google Gemini LLM Fallback & Response Generator for AP Auditor Chatbot.
Provides conversational assistance for GENERAL intent queries and open-ended questions
using the Google Generative AI SDK with model gemini-2.0-flash.
Also dynamically generates natural conversational replies grounded in real AP data.
Falls back gracefully if the GEMINI_API_KEY is unconfigured, placeholder, or invalid.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

import google.generativeai as genai

from ..api.stats import get_stats
from .gemini_client import (
    call_gemini,
    clean_json_markdown,
    get_gemini_api_key,
    get_gemini_model,
)
from .response_formatter import format_response

logger = logging.getLogger(__name__)

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

INVOICE_REGEX = re.compile(r"\b(INV-\d+)\b", re.IGNORECASE)


def classify_with_gemini(user_message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Tier 2 LLM classifier using Google Gemini with multi-model fallback.
    Extracts structured intent and invoice_id in strict JSON.
    Gracefully handles missing keys, network timeouts, and markdown fences.
    """
    api_key = get_gemini_api_key() or os.environ.get("GEMINI_API_KEY")
    dummy_keys = {"my-actual-key-goes-here", "your_gemini_api_key_here", "your-api-key-here", ""}
    
    if not api_key or api_key.strip() in dummy_keys:
        inv_match = INVOICE_REGEX.search(user_message)
        entities: Dict[str, Any] = {
            "tier": 2,
            "llm_handled": False,
            "fallback_reason": "No valid Gemini API key configured.",
        }
        if inv_match:
            entities["invoice_id"] = inv_match.group(1).upper()
        return "GENERAL", entities

    system_prompt = (
        "You are an intent classifier for AP Auditor, an enterprise Accounts Payable audit copilot. "
        "Classify the user message into exactly one of these intents: "
        "CHECK_STATUS, SHOW_FLAGGED, EXPLAIN_INVOICE, APPROVE_INVOICE, "
        "REJECT_INVOICE, SHOW_STATS, EXPORT_REPORT, GENERAL. "
        "Also extract any invoice ID mentioned (e.g. INV-1002). "
        "Respond in strict JSON only: {\"intent\": string, \"invoice_id\": string or null}"
    )

    try:
        raw_text = call_gemini(
            f"{system_prompt}\n\nUser message: {user_message}\n\nRespond in strict JSON only: {{\"intent\": string, \"invoice_id\": string or null}}"
        )

        if not raw_text:
            inv_match = INVOICE_REGEX.search(user_message)
            entities = {"tier": 2, "llm_handled": False, "fallback_reason": "Empty Gemini response"}
            if inv_match:
                entities["invoice_id"] = inv_match.group(1).upper()
            return "GENERAL", entities

        # Strip any markdown code fences first (Gemini sometimes wraps JSON in ```json blocks)
        cleaned_text = clean_json_markdown(raw_text)

        try:
            parsed = json.loads(cleaned_text)
        except Exception as json_err:
            logger.warning(f"Failed to parse Gemini JSON output '{cleaned_text}': {json_err}")
            parsed = {}

        intent = parsed.get("intent", "GENERAL")
        if not isinstance(intent, str) or intent.strip().upper() not in VALID_INTENTS:
            intent = "GENERAL"
        else:
            intent = intent.strip().upper()

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
        logger.warning(f"Gemini intent classification call failed: {e}")
        inv_match = INVOICE_REGEX.search(user_message)
        entities = {"tier": 2, "llm_handled": False, "error": str(e)}
        if inv_match:
            entities["invoice_id"] = inv_match.group(1).upper()
        return "GENERAL", entities


DEFAULT_GUIDE = (
    "Hello! I am your **AP Auditor AI Copilot**. I help Accounts Payable teams review invoices, "
    "catch fraud and duplicates, and maintain a compliance audit trail.\n\n"
    "Here are some things you can ask me:\n"
    "• **'show stats'** — view compliance metrics, pass rates, and exception volume\n"
    "• **'show flagged invoices'** — view invoices in the human review queue\n"
    "• **'why was INV-1002 flagged'** — inspect rule violations and evidence for a specific invoice\n"
    "• **'approve INV-1002'** or **'reject INV-1002'** — submit an auditor decision\n"
    "• **'check status'** — inspect system audit status\n"
    "• **'export report'** — generate and download an audit exceptions report"
)


def handle_llm_fallback(user_message: str, stats_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Calls Google Gemini with automatic model failover for open-ended queries using system AP context.
    If GEMINI_API_KEY is missing, placeholder, or call fails, returns a graceful fallback guide.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return (
            "🤖 **AP Auditor AI Copilot**\n\n"
            "I'm currently running in **Tier 1 (Rules Engine Mode)** because a Google Gemini API key has not been configured yet.\n\n"
            "🔑 **To activate Gemini (Tier 2 Conversational AI):**\n"
            "1. Open `backend/.env`\n"
            "2. Replace `GEMINI_API_KEY=my-actual-key-goes-here` with your real key from [Google AI Studio](https://aistudio.google.com/app/apikey)\n"
            "3. Save the file (it connects immediately, no server restart needed!)\n\n"
            "⚡ **Instant commands ready right now:**\n"
            "• **'show stats'** — view compliance metrics and totals\n"
            "• **'show flagged invoices'** — view review queue exceptions\n"
            "• **'why was INV-3918 flagged'** — inspect rule violations for an invoice\n"
            "• **'approve INV-1002'** or **'reject INV-1002'** — record audit decisions\n"
            "• **'export report'** — generate audit report"
        )

    if not stats_context:
        try:
            stats_context = get_stats()
        except Exception:
            stats_context = {}

    system_prompt = (
        "You are the AI Copilot for AP-Auditor, an enterprise Accounts-Payable Exception Checker. "
        "You help human auditors review invoice compliance, duplicate submissions, spend limits, "
        "and vendor bank discrepancies. Maintain a professional, concise, and helpful tone.\n\n"
        f"Current System State Context:\n{stats_context}\n"
    )

    try:
        content = call_gemini(
            f"{system_prompt}\n\nUser question: {user_message}\n\nRespond helpfully and concisely."
        )
        return content.strip() if content else DEFAULT_GUIDE

    except Exception as e:
        return (
            f"I encountered an issue connecting to the AI language service ({str(e)}).\n\n"
            "You can continue using all AP auditor commands like 'show stats', "
            "'show flagged invoices', 'why was INV-1002 flagged', or 'export report'."
        )


def generate_conversational_reply(
    user_message: str,
    intent: str,
    status: str,
    raw_data: Optional[Dict[str, Any]],
) -> str:
    """
    Generates a natural, intelligent conversational reply.
    Prompts Gemini to formulate a rich, business-grade explanation grounded
    directly in the retrieved AP data.
    If Gemini is not available or encounters an error, uses deterministic template formatting.
    """
    base_reply = format_response(intent, status, raw_data)

    api_key = get_gemini_api_key()
    if not api_key or not raw_data or status != "SUCCESS":
        return base_reply

    system_prompt = (
        "You are AP Auditor AI Copilot, an enterprise Accounts Payable auditing assistant. "
        "Formulate a direct, natural, professional response to the user's question, grounded "
        "strictly in the verified AP data provided. "
        "Be concise (2-4 sentences or clear bullet points), accurate, and helpful. "
        "Never hallucinate invoice numbers or currency amounts."
    )

    prompt = (
        f"{system_prompt}\n\n"
        f"User question: {user_message}\n"
        f"Classified Intent: {intent}\n"
        f"Execution Status: {status}\n"
        f"Verified AP Data Payload:\n{raw_data}\n\n"
        "Draft the final response to the user:"
    )

    try:
        content = call_gemini(prompt)
        return content.strip() if content else base_reply
    except Exception:
        return base_reply


def handle_azure_fallback(user_message: str, stats_context: Optional[Dict[str, Any]] = None) -> str:
    """Backward compatibility alias."""
    return handle_llm_fallback(user_message, stats_context)
