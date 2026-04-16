"""
AI service with dual provider support (OpenAI-compatible + Anthropic).

The OpenAI-compatible path works with OpenRouter, OpenAI, Groq, Together, etc.
and unlocks cheaper models (gpt-4o-mini, gemini-2.5-flash, llama-3.3).
The Anthropic path is kept for Claude-only deployments.

Switch via AI_PROVIDER env var.
"""
import json
from typing import AsyncIterator

import anthropic
import openai

from app.config import settings
from app.models.business import Business
from app.models.message import Message


# ISO code → friendly name for the system prompt
LANGUAGE_NAMES = {
    "es": "Spanish (Español)",
    "en": "English",
    "ca": "Catalan (Català)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "it": "Italian (Italiano)",
    "pt": "Portuguese (Português)",
}


def _build_system_prompt(business: Business, language: str = "es") -> str:
    """Build a system prompt with the business context and target language."""
    schedule = business.schedule or "{}"
    try:
        schedule_formatted = json.dumps(json.loads(schedule), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        schedule_formatted = schedule

    language_name = LANGUAGE_NAMES.get(language, language)

    return f"""You are the virtual assistant of "{business.name}". Your role is to help customers with their questions in a friendly, professional and concise way.

Business information:
- Name: {business.name}
- Description: {business.description}
- Address: {business.address}
- Phone: {business.phone}
- Email: {business.email}
- Schedule: {schedule_formatted}

Additional info:
{business.extra_info}

Rules:
- Respond ONLY with information about this business. Do not invent facts.
- If you don't have the information to answer, kindly say so and suggest contacting the business directly using the phone or email above.
- IMPORTANT: You MUST respond in {language_name} regardless of what language the user writes in.
- Be concise: max 2-3 sentences per reply unless more detail is required.
"""


def _build_messages(conversation_history: list[Message], user_message: str) -> list[dict]:
    """Convert conversation history to API message format."""
    messages = []
    for msg in conversation_history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


# ── Clients ───────────────────────────────────────────────────────────────

def _use_openai() -> bool:
    return (settings.AI_PROVIDER or "openai").lower() == "openai"


def _get_openai_client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY,
        base_url=settings.OPENAI_BASE_URL or None,
    )


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    kwargs = {"api_key": settings.ANTHROPIC_API_KEY}
    if settings.ANTHROPIC_BASE_URL:
        kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
    return anthropic.AsyncAnthropic(**kwargs)


def _get_client():
    """Legacy export used by other services for simple JSON tasks.
    Returns the provider-appropriate client.
    """
    if _use_openai():
        return _get_openai_client()
    return _get_anthropic_client()


# ── High-level calls ──────────────────────────────────────────────────────

async def _openai_chat(system: str, messages: list[dict], max_tokens: int = 500) -> tuple[str, int | None, int | None]:
    client = _get_openai_client()
    resp = await client.chat.completions.create(
        model=settings.AI_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}] + messages,
    )
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    return text, (usage.prompt_tokens if usage else None), (usage.completion_tokens if usage else None)


async def _anthropic_chat(system: str, messages: list[dict], max_tokens: int = 500) -> tuple[str, int | None, int | None]:
    client = _get_anthropic_client()
    resp = await client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    text = resp.content[0].text
    usage = getattr(resp, "usage", None)
    return text, (usage.input_tokens if usage else None), (usage.output_tokens if usage else None)


class AIError(Exception):
    """Raised when the AI provider fails. Callers handle fallback + logging."""


def ai_fallback_message(business: Business) -> str:
    return (
        f"Lo siento, no puedo responder a eso ahora mismo. "
        f"Puedes contactarnos en {business.phone} o {business.email}."
    )


async def generate_ai_response(
    business: Business,
    conversation_history: list[Message],
    user_message: str,
    language: str = "es",
) -> tuple[str, int | None, int | None]:
    """Generate a response and return (text, tokens_in, tokens_out).
    Raises AIError on provider failure — the caller decides how to recover
    (typically: log an incident and fall back to a canned message).
    """
    system_prompt = _build_system_prompt(business, language)
    messages = _build_messages(conversation_history, user_message)

    try:
        if _use_openai():
            return await _openai_chat(system_prompt, messages)
        return await _anthropic_chat(system_prompt, messages)
    except Exception as e:
        raise AIError(f"{type(e).__name__}: {e}") from e


async def stream_ai_response(
    business: Business,
    conversation_history: list[Message],
    user_message: str,
    language: str = "es",
    usage_out: dict | None = None,
) -> AsyncIterator[str]:
    """Yield text chunks. If usage_out dict is passed, populate it with
    {'tokens_in': int, 'tokens_out': int} once the stream finishes.
    """
    system_prompt = _build_system_prompt(business, language)
    messages = _build_messages(conversation_history, user_message)

    try:
        if _use_openai():
            client = _get_openai_client()
            stream = await client.chat.completions.create(
                model=settings.AI_MODEL,
                max_tokens=500,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                # Last chunk carries usage (when include_usage=True)
                if usage_out is not None and getattr(chunk, "usage", None):
                    usage_out["tokens_in"] = chunk.usage.prompt_tokens
                    usage_out["tokens_out"] = chunk.usage.completion_tokens
        else:
            client = _get_anthropic_client()
            async with client.messages.stream(
                model=settings.AI_MODEL,
                max_tokens=500,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                if usage_out is not None:
                    final = await stream.get_final_message()
                    u = getattr(final, "usage", None)
                    if u:
                        usage_out["tokens_in"] = u.input_tokens
                        usage_out["tokens_out"] = u.output_tokens
    except Exception as e:
        # Surface the error via the shared usage dict so the caller can log it
        if usage_out is not None:
            usage_out["_error"] = f"{type(e).__name__}: {e}"
        print(f"[AI Stream Error] {type(e).__name__}: {e}")
        yield ai_fallback_message(business)


# ── JSON-only helper used by translation services ────────────────────────

async def chat_json(system: str, user: str, max_tokens: int = 2000) -> str:
    """One-shot call for translation services that need raw text back.
    Uses the configured provider. Returns the raw assistant message string.
    """
    if _use_openai():
        client = _get_openai_client()
        resp = await client.chat.completions.create(
            model=settings.AI_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""
    client = _get_anthropic_client()
    resp = await client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text
