"""
Central OpenAI / Azure OpenAI Client and Configuration Provider for AP Auditor.
Dynamically reads API keys and endpoints from backend/.env or root .env on disk
so changes take effect immediately without requiring a uvicorn server restart.
Supports Azure OpenAI as well as direct OpenAI.
"""

import os
from pathlib import Path
from typing import Optional, Tuple
from dotenv import dotenv_values


def get_llm_config() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns (provider, api_key, endpoint_or_deployment).
    provider: 'azure', 'openai', or None.
    """
    candidates = [
        Path(__file__).resolve().parent.parent.parent / ".env",          # backend/.env
        Path(__file__).resolve().parent.parent.parent.parent / ".env",   # root .env
    ]
    env_vals = {}
    for env_path in candidates:
        if env_path.exists():
            try:
                env_vals.update(dotenv_values(env_path))
            except Exception:
                pass

    # Check Azure OpenAI
    azure_key = env_vals.get("AZURE_OPENAI_KEY") or env_vals.get("AZURE_OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    azure_endpoint = env_vals.get("AZURE_OPENAI_ENDPOINT") or os.environ.get("AZURE_OPENAI_ENDPOINT")

    dummy_keys = ("my-actual-key-goes-here", "your_openai_api_key_here", "your-api-key-here", "your_azure_key_here")

    if azure_key and azure_key.strip() and azure_key.strip() not in dummy_keys and azure_endpoint:
        return "azure", azure_key.strip(), azure_endpoint.strip()

    # Check Direct OpenAI
    openai_key = env_vals.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if openai_key and openai_key.strip() and openai_key.strip() not in dummy_keys:
        return "openai", openai_key.strip(), None

    return None, None, None


def get_openai_client():
    """
    Returns an initialized AzureOpenAI or OpenAI client if credentials exist, else None.
    """
    provider, key, endpoint = get_llm_config()
    if not provider:
        return None

    try:
        if provider == "azure":
            from openai import AzureOpenAI
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
            return AzureOpenAI(
                api_key=key,
                azure_endpoint=endpoint,
                api_version=api_version,
            )
        else:
            from openai import OpenAI
            return OpenAI(api_key=key)
    except Exception:
        return None


def get_llm_model_name() -> str:
    """Returns deployment or model name."""
    provider, _, _ = get_llm_config()
    if provider == "azure":
        return os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    return "gpt-4o-mini"
