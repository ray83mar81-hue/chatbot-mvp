"""AI service with dual provider support (OpenAI-compatible + Anthropic).

The OpenAI-compatible path works with OpenRouter, OpenAI, Groq, Together, etc.
and unlocks cheaper models (gpt-4o-mini, gemini-2.5-flash, llama-3.3).
The Anthropic path is kept for Claude-only deployments.

Switch via AI_PROVIDER env var.

After the intent refactor, this service is the ONLY source of chat replies:
the caller passes the active `language` and the business, and the system
prompt is built from the LOCALIZED business fields (BusinessTranslation row
for that language, with fallback to the base Business columns when empty).
"""
import json
from typing import AsyncIterator

import anthropic
import openai
from sqlalchemy.orm import Session

from app.config import settings
from app.models.business import Business
from app.models.business_translation import BusinessTranslation
from app.models.message import Message


LANGUAGE_NAMES = {
    "es": "Spanish (Español)",
    "en": "English",
    "ca": "Catalan (Català)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "it": "Italian (Italiano)",
    "pt": "Portuguese (Português)",
}


def _get_localized_fields(db: Session, business: Business, language: str) -> dict:
    """Resolve the business fields in the target `language`, falling back to
    the base Business columns per field when a translated value is empty.
    """
    translation = (
        db.query(BusinessTranslation)
        .filter(
            BusinessTranslation.business_id == business.id,
            BusinessTranslation.language_code == language,
        )
        .first()
    )

    def pick(tr_val, base_val) -> str:
        v = (tr_val or "").strip()
        return v if v else (base_val or "")

    return {
        "name":        pick(translation.name        if translation else None, business.name),
        "description": pick(translation.description if translation else None, business.description),
        "address":     pick(translation.address     if translation else None, business.address),
        "schedule":    pick(translation.schedule    if translation else None, business.schedule),
        "extra_info":  pick(translation.extra_info  if translation else None, business.extra_info),
        # Non-translatable
        "phone": business.phone or "",
        "email": business.email or "",
    }


def _build_system_prompt(fields: dict, language: str) -> str:
    """Compose the system prompt from pre-resolved localized fields."""
    schedule = fields.get("schedule") or "{}"
    try:
        schedule_formatted = json.dumps(json.loads(schedule), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        schedule_formatted = schedule

    language_name = LANGUAGE_NAMES.get(language, language)

    return f"""You are the virtual assistant of "{fields['name']}". Your role is to help customers with their questions in a friendly, professional and concise way.

Business information:
- Name: {fields['name']}
- Description: {fields['description']}
- Address: {fields['address']}
- Phone: {fields['phone']}
- Email: {fields['email']}
- Schedule: {schedule_formatted}

Additional info:
{fields['extra_info']}

Rules:
- Respond ONLY with information about this business. Do not invent facts.
- If you don't have the information to answer, kindly say so and suggest contacting the business directly using the phone or email above.
- IMPORTANT: You MUST respond in {language_name} regardless of what language the user writes in.
- Be concise: max 2-3 sentences per reply unless more detail is required.
"""


def _build_messages(conversation_history: list[Message], user_message: str) -> list[dict]:
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
    """Legacy export used by other services for simple JSON tasks."""
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
    db: Session,
    conversation_history: list[Message],
    user_message: str,
    language: str = "es",
) -> tuple[str, int | None, int | None]:
    """Generate a reply in `language`. Returns (text, tokens_in, tokens_out)."""
    fields = _get_localized_fields(db, business, language)
    system_prompt = _build_system_prompt(fields, language)
    messages = _build_messages(conversation_history, user_message)

    try:
        if _use_openai():
            return await _openai_chat(system_prompt, messages)
        return await _anthropic_chat(system_prompt, messages)
    except Exception as e:
        raise AIError(f"{type(e).__name__}: {e}") from e


async def stream_ai_response(
    business: Business,
    db: Session,
    conversation_history: list[Message],
    user_message: str,
    language: str = "es",
    usage_out: dict | None = None,
) -> AsyncIterator[str]:
    """Yield text chunks. Populates usage_out with tokens if given."""
    fields = _get_localized_fields(db, business, language)
    system_prompt = _build_system_prompt(fields, language)
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
        if usage_out is not None:
            usage_out["_error"] = f"{type(e).__name__}: {e}"
        print(f"[AI Stream Error] {type(e).__name__}: {e}")
        yield ai_fallback_message(business)


# ── JSON-only helper used by translation services ────────────────────────

async def chat_json(system: str, user: str, max_tokens: int = 2000) -> str:
    """One-shot call for translation services that need raw text back."""
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
