"""Shared helpers for AI-driven translation services.

This module used to host the intent-translation workflow. After the intent
system was removed (AI-first refactor) only the utilities survive here and
are consumed by business_translation_service and conversations routers.
"""
import json
import re


class TranslationError(Exception):
    """Raised when an AI translation response cannot be parsed."""


def _extract_json(text: str) -> dict:
    """Robustly extract a JSON object from the model's reply.

    Handles ```json ... ``` fences and stray prose around the JSON body.
    """
    text = text.strip()

    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            text = text[first : last + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise TranslationError(f"AI response was not valid JSON: {e}") from e
