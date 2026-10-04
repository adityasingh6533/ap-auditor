"""
Chatbot package for AP Auditor.
Contains intent classification, query routing, response formatting, and Azure OpenAI fallback.
"""

from .intent_classifier import classify_intent
from .query_router import handle_intent
from .response_formatter import format_response
from .azure_openai_fallback import handle_azure_fallback
from .llm_fallback import handle_llm_fallback

__all__ = [
    "classify_intent",
    "handle_intent",
    "format_response",
    "handle_azure_fallback",
    "handle_llm_fallback",
]
