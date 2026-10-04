"""
OpenAI LLM Fallback & Response Generator for AP Auditor Chatbot.
Provides conversational assistance for GENERAL intent queries and open-ended questions
using the standard OpenAI Python SDK with model gpt-4o-mini.
Also dynamically generates natural conversational replies grounded in real AP data.
Falls back gracefully if the API key is unconfigured, placeholder, or invalid.
"""

import json
from typing import Any, Dict, Optional
from ..api.stats import get_stats
from .openai_client import get_openai_client
from .response_formatter import format_response


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
    Calls OpenAI gpt-4o-mini for open-ended queries using system AP context.
    If OPENAI_API_KEY is missing, placeholder, or call fails, returns a graceful fallback guide.
    """
    client = get_openai_client()
    if client is None:
        return DEFAULT_GUIDE

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
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=350,
            temperature=0.3,
        )
        content = response.choices[0].message.content
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
    If OpenAI is available, prompts gpt-4o-mini to formulate a rich, business-grade
    explanation grounded directly in the retrieved AP data.
    If OpenAI is not available, uses deterministic template formatting.
    """
    base_reply = format_response(intent, status, raw_data)

    client = get_openai_client()
    if client is None or not raw_data or status != "SUCCESS":
        return base_reply

    # Let OpenAI generate a natural conversational answer grounded in raw_data
    system_prompt = (
        "You are AP Auditor AI Copilot, an enterprise Accounts Payable auditing assistant. "
        "Formulate a direct, natural, professional response to the user's question, grounded "
        "strictly in the verified AP data provided. "
        "Be concise (2-4 sentences or clear bullet points), accurate, and helpful. "
        "Never hallucinate invoice numbers or currency amounts."
    )

    prompt = (
        f"User question: {user_message}\n"
        f"Classified Intent: {intent}\n"
        f"System AP Data: {json.dumps(raw_data, default=str)}\n"
        f"Standard summary reference:\n{base_reply}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=250,
            temperature=0.3,
        )
        content = response.choices[0].message.content
        if content and content.strip():
            return content.strip()
    except Exception:
        pass

    return base_reply


# Backward-compatibility alias
handle_azure_fallback = handle_llm_fallback
