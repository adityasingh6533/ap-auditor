"""
Backward-compatibility stub for azure_openai_fallback.
Delegates directly to llm_fallback.py powered by direct OpenAI.
"""

from .llm_fallback import handle_azure_fallback, handle_llm_fallback

__all__ = ["handle_azure_fallback", "handle_llm_fallback"]
