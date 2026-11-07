"""Pick a Gemini chat model that actually exists for this API key.

Google retires and renames Gemini models often. Instead of failing with NotFound when the
configured CHAT_MODEL disappears, ask the API which models support generateContent and fall
back to the closest available Flash model.
"""
import logging
import re
from typing import List, Optional

import google.generativeai as genai

from app.ai.config import ai_settings

logger = logging.getLogger(__name__)

# Most preferred first. Names are matched without the "models/" prefix.
FALLBACK_PREFERENCE = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]

_resolved: Optional[str] = None


def _available_models() -> List[str]:
    names = []
    for m in genai.list_models():
        if "generateContent" in getattr(m, "supported_generation_methods", []):
            names.append(m.name.removeprefix("models/"))
    return names


def _pick(configured: str, available: List[str]) -> str:
    if configured in available:
        return configured
    for name in FALLBACK_PREFERENCE:
        if name in available:
            return name
    # Newest-looking stable Flash model (skip previews/experimental/image/tts/live variants).
    flash = [
        n for n in available
        if "flash" in n and not any(x in n for x in ("preview", "exp", "image", "tts", "live", "thinking"))
    ]
    if flash:
        return sorted(flash, reverse=True)[0]
    return configured


def resolve_chat_model() -> str:
    """Return a usable chat model name (cached after the first successful lookup)."""
    global _resolved
    if _resolved:
        return _resolved
    configured = ai_settings.chat_model.removeprefix("models/")
    try:
        genai.configure(api_key=ai_settings.google_api_key)
        available = _available_models()
        _resolved = _pick(configured, available)
        if _resolved != configured:
            logger.warning("Chat model %s is not available; using %s instead", configured, _resolved)
    except Exception:
        logger.exception("Could not list Gemini models; using configured %s", configured)
        return configured
    return _resolved


def resolved_model() -> Optional[str]:
    """The model chosen so far (None until the first chat request resolves it)."""
    return _resolved


def replacement_from_error(error: Exception) -> Optional[str]:
    """If Gemini says a model is retired ("... use models/X ..."), switch to X and return it."""
    global _resolved
    match = re.search(r"no longer available.*?use (?:models/)?([\w.-]+)", str(error), re.S)
    if not match:
        return None
    _resolved = match.group(1).rstrip(".")
    logger.warning("Gemini retired the current model; switching to %s", _resolved)
    return _resolved
