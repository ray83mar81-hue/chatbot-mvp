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

async def _openai_chat(system: str, messages: list[dict], max_tokens: int = 500) -> str:
    client = _get_openai_client()
    resp = await client.chat.completions.create(
        model=settings.AI_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return resp.choices[0].message.content or ""


async def _anthropic_chat(system: str, messages: list[dict], max_tokens: int = 500) -> str:
    client = _get_anthropic_client()
    resp = await client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return resp.content[0].text


async def generate_ai_response(
    business: Business,
    conversation_history: list[Message],
    user_message: str,
    language: str = "es",
) -> str:
    """Generate a response using the configured provider (OpenAI or Anthropic)."""
    system_prompt = _build_system_prompt(business, language)
    messages = _build_messages(conversation_history, user_message)

    try:
        if _use_openai():
            return await _openai_chat(system_prompt, messages)
        return await _anthropic_chat(system_prompt, messages)
    except Exception as e:
        print(f"[AI Error] {type(e).__name__}: {e}")
        return (
            f"Lo siento, no puedo responder a eso ahora mismo. "
            f"Puedes contactarnos en {business.phone} o {business.email}."
        )


async def stream_ai_response(
    business: Business,
    conversation_history: list[Message],
    user_message: str,
    language: str = "es",
) -> AsyncIterator[str]:
    """Yield text chunks from the configured provider's streaming API."""
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
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
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
    except Exception as e:
        print(f"[AI Stream Error] {type(e).__name__}: {e}")
        yield (
            f"Lo siento, no puedo responder a eso ahora mismo. "
            f"Puedes contactarnos en {business.phone} o {business.email}."
        )


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
