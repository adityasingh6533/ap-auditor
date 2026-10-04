"""
Central Google Gemini Client and Configuration Provider for AP Auditor Chatbot.
Dynamically reads GEMINI_API_KEY from backend/.env or root .env on disk
so key additions take effect immediately without requiring a server restart.
Configures google.generativeai with model gemini-2.0-flash.
"""

import os
from pathlib import Path
import re
from typing import Optional
from dotenv import dotenv_values

DUMMY_KEYS = {
    "my-actual-key-goes-here",
    "your_gemini_api_key_here",
    "your-api-key-here",
    "your_key_here",
    "",
}


def get_gemini_api_key() -> Optional[str]:
    """
    Retrieves the Gemini API key from .env files or os.environ.
    Checks dynamically on disk so changes take effect without server restart.
    """
    candidates = [
        Path(__file__).resolve().parent.parent.parent / ".env",          # backend/.env
        Path(__file__).resolve().parent.parent.parent.parent / ".env",   # root .env
    ]
    for env_path in candidates:
        if env_path.exists():
            try:
                vals = dotenv_values(env_path)
                k = vals.get("GEMINI_API_KEY")
                if k and k.strip() and k.strip().lower() not in DUMMY_KEYS:
                    os.environ["GEMINI_API_KEY"] = k.strip()
                    return k.strip()
            except Exception:
                pass

    env_k = os.environ.get("GEMINI_API_KEY")
    if env_k and env_k.strip() and env_k.strip().lower() not in DUMMY_KEYS:
        return env_k.strip()

    return None


def get_gemini_model(model_name: str = "gemini-2.5-flash"):
    """
    Returns an initialized GenerativeModel instance if a valid key is present.
    Uses active Google Gemini models (gemini-2.5-flash, gemini-flash-latest, gemini-3.8-flash).
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        # Prioritize active production models
        candidates = [model_name, "gemini-2.5-flash", "gemini-flash-latest", "gemini-3.8-flash"]
        seen = set()
        for m in candidates:
            if m and m not in seen and m != "gemini-2.0-flash":
                seen.add(m)
                try:
                    return genai.GenerativeModel(m)
                except Exception:
                    continue
        return genai.GenerativeModel("gemini-2.5-flash")
    except Exception:
        return None


def clean_json_markdown(text: str) -> str:
    """
    Strips markdown code fences (```json ... ``` or ``` ... ```) from Gemini LLM output
    so json.loads can parse cleanly without error.
    """
    cleaned = text.strip()
    # Match standard ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback strip leading/trailing backticks
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    return cleaned


def check_gemini_status() -> dict:
    """
    Diagnostic helper to verify whether GEMINI_API_KEY is configured,
    whether it's a placeholder, and tests live connectivity.
    """
    api_key = get_gemini_api_key()
    raw_env_key = os.environ.get("GEMINI_API_KEY", "")
    
    backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
    raw_file_key = ""
    if backend_env.exists():
        try:
            vals = dotenv_values(backend_env)
            raw_file_key = vals.get("GEMINI_API_KEY", "") or ""
        except Exception:
            pass

    active_raw = raw_file_key or raw_env_key or ""
    is_placeholder = active_raw.strip().lower() in DUMMY_KEYS or not active_raw.strip()
    
    status_info = {
        "provider": "google-gemini",
        "model": "gemini-2.5-flash",
        "api_key_configured": bool(api_key),
        "is_placeholder": is_placeholder,
        "key_source": "backend/.env" if raw_file_key else ("os.environ" if raw_env_key else "none"),
        "key_preview": (active_raw[:8] + "..." + active_raw[-4:]) if len(active_raw) > 12 else active_raw,
        "tier1_rules_engine": "ACTIVE (zero-latency keyword & regex matching)",
        "tier2_llm_engine": "ONLINE (gemini-2.5-flash active)" if api_key else "STANDBY (awaiting valid Gemini API key in backend/.env)",
    }

    if api_key:
        try:
            model = get_gemini_model("gemini-2.5-flash")
            if model:
                res = model.generate_content("ping", generation_config={"max_output_tokens": 5})
                status_info["connection_test"] = "SUCCESS"
                status_info["gemini_ready"] = True
            else:
                status_info["connection_test"] = "FAILED: Could not initialize model"
                status_info["gemini_ready"] = False
        except Exception as e:
            status_info["connection_test"] = f"FAILED: {str(e)}"
            status_info["gemini_ready"] = False
    else:
        status_info["connection_test"] = "SKIPPED (no active key)"
        status_info["gemini_ready"] = False
        status_info["instruction"] = "Replace 'GEMINI_API_KEY=my-actual-key-goes-here' in backend/.env with your Google AI Studio API key (https://aistudio.google.com/app/apikey)."

    return status_info

