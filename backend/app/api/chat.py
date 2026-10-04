"""
Chat API Router for AP Auditor.
Exposes the conversational AI assistant endpoint for invoice queries and actions.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..chatbot.azure_openai_fallback import handle_azure_fallback
from ..chatbot.intent_classifier import classify_intent
from ..chatbot.query_router import handle_intent
from ..chatbot.response_formatter import format_response

router = APIRouter(prefix="/api", tags=["Chat"])


class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="Conversational query or command from the user")


class ChatMessageResponse(BaseModel):
    reply: str = Field(..., description="Natural language response text")
    intent: str = Field(..., description="Classified intent tag")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured payload for frontend card/table rendering")


@router.post("/chat", response_model=ChatMessageResponse)
def chat_endpoint(payload: ChatMessageRequest) -> ChatMessageResponse:
    """
    Processes incoming natural language messages, extracts entities, executes appropriate
    rules/database actions, and returns formatted responses with optional structured data.
    """
    user_msg = payload.message.strip()
    intent, entities = classify_intent(user_msg)

    # If general inquiry or open-ended question, use the fallback handler
    if intent == "GENERAL":
        reply = handle_azure_fallback(user_msg)
        return ChatMessageResponse(reply=reply, intent=intent, data=None)

    # Route intent to internal functions
    status, raw_data = handle_intent(intent, entities)

    # If router fell back, use azure fallback
    if status == "FALLBACK":
        reply = handle_azure_fallback(user_msg)
        return ChatMessageResponse(reply=reply, intent=intent, data=None)

    # Format natural language reply
    reply = format_response(intent, status, raw_data)

    return ChatMessageResponse(
        reply=reply,
        intent=intent,
        data=raw_data,
    )
