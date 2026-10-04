"""
Azure OpenAI Fallback Handler for Open-Ended Conversational Questions.
Provides contextual assistance for GENERAL intent queries and falls back gracefully
if credentials are not yet provisioned.
"""

import os
from typing import Any, Dict, Optional
from ..api.stats import get_stats


def handle_azure_fallback(user_message: str, stats_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Attempts to call Azure OpenAI for open-ended queries using system AP context.
    If Azure OpenAI credentials are missing or call fails, returns a graceful fallback guide.
    """
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = (
        os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        or "gpt-4o"
    )
    api_version = os.getenv("OPENAI_API_VERSION") or "2024-02-15-preview"

    # Standard OpenAI fallback if Azure is not configured
    standard_api_key = os.getenv("OPENAI_API_KEY")

    if not api_key and not standard_api_key:
        return (
            "Hello! I am your **AP Auditor AI Copilot**. I help Accounts Payable teams review invoices, "
            "catch fraud and duplicates, and maintain a compliance audit trail.\n\n"
            "Here are some things you can ask me:\n"
            "• **'give me a summary'** — view compliance metrics, pass rates, and exception volume\n"
            "• **'show me flagged invoices'** — view invoices in the human review queue\n"
            "• **'why was INV-3918 flagged'** — inspect rule violations and evidence for a specific invoice\n"
            "• **'approve INV-3918'** or **'reject INV-3918'** — submit an auditor decision\n"
            "• **'check invoices'** — inspect system audit status"
        )

    # Fetch stats context if not supplied
    if not stats_context:
        try:
            stats_context = get_stats()
        except Exception:
            stats_context = {}

    system_prompt = (
        "You are the AI Copilot for AP-Auditor, an industrial Accounts-Payable Exception Checker. "
        "You help human auditors review invoice compliance, duplicate submissions, spend limits, "
        "and vendor bank discrepancies. Maintain a professional, concise, and helpful tone.\n\n"
        f"Current System State Context:\n{stats_context}\n"
    )

    try:
        if api_key and endpoint:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
            )
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=350,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()

        elif standard_api_key:
            from openai import OpenAI
            client = OpenAI(api_key=standard_api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=350,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()

    except Exception as e:
        return (
            f"I encountered an issue connecting to the AI language service: {str(e)}.\n\n"
            "You can still use all built-in AP auditor commands like 'give me a summary', "
            "'show me flagged invoices', or 'why was INV-3918 flagged'."
        )

    return "How can I assist you with accounts payable auditing today?"
