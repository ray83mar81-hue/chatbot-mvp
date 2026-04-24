"""AI service with dual provider support (OpenAI-compatible + Anthropic).

Per-tenant configuration (Fase 5): each Business can set its own provider,
model, API key and optional base_url. When nothing is configured on the
business, the global env vars (settings.AI_*) are used as a sensible default,
which keeps existing deployments untouched.

Supported providers, grouped by SDK family:
  - OpenAI-compatible path (openai.AsyncOpenAI): "openai", "openrouter",
    "gemini" (via the OpenAI-compatible endpoint), "grok", "custom".
  - Native Anthropic path (anthropic.AsyncAnthropic): "anthropic".

The user sees 6 provider options in the admin; under the hood there are only
two code paths.
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


# Supported languages for the chatbot. This dict is the single source of
# truth for (a) the system prompt ("respond in {name}") and (b) the
# per-tenant language allow-list enforced at the API boundary. To add a new
# language: append a row here, add a matching row to DEFAULT_LANGUAGES in
# main.py (with native_name/flag_emoji), and redeploy — that's it.
#
# Why this set: target market is Spain + immediate EU neighbours. Mainstream
# European languages give predictable, high-quality AI output across every
# model we support. Niche languages (RU/AR/ZH…) would work on some models
# but are inconsistent and risk embarrassing the client.
LANGUAGE_NAMES = {
    "es": "Spanish (Español)",
    "en": "English",
    "ca": "Catalan (Català)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "it": "Italian (Italiano)",
    "pt": "Portuguese (Português)",
}

# Allow-list of language codes a tenant is permitted to activate. Frozen so
# callers can `in`-check without accidental mutation. Derived from the names
# dict above to guarantee the two stay in sync.
ALLOWED_LANGUAGE_CODES: frozenset[str] = frozenset(LANGUAGE_NAMES.keys())


# ── Per-tenant config resolution ──────────────────────────────────────────

_DEFAULT_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "gemini":     "https://generativelanguage.googleapis.com/v1beta/openai/",
    "grok":       "https://api.x.ai/v1",
    # "openai" and "anthropic" use the SDK default (None).
    # "custom" uses business.ai_base_url.
}


def _resolve_ai_config(business: Business) -> dict:
    """Effective AI config for this business.

    If the business has no `ai_provider` set, the global env config is used
    verbatim (provider + model + key + base_url + prices). If a provider is
    set, we use the business values with targeted fallback per field.
    """
    if not business.ai_provider:
        provider = (settings.AI_PROVIDER or "openai").lower()
        sdk = "anthropic" if provider == "anthropic" else "openai"
        return {
            "provider": provider,
            "sdk": sdk,
            "model": settings.AI_MODEL,
            "api_key": (settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY or ""),
            "base_url": (
                settings.OPENAI_BASE_URL if sdk == "openai"
                else settings.ANTHROPIC_BASE_URL
            ) or None,
            "input_price_per_million": settings.AI_PRICE_INPUT_PER_MILLION,
            "output_price_per_million": settings.AI_PRICE_OUTPUT_PER_MILLION,
        }

    provider = business.ai_provider.lower()
    sdk = "anthropic" if provider == "anthropic" else "openai"

    if provider == "custom":
        base_url = business.ai_base_url or None
    elif provider == "openai":
        base_url = settings.OPENAI_BASE_URL or None
    elif provider == "anthropic":
        base_url = settings.ANTHROPIC_BASE_URL or None
    else:
        base_url = _DEFAULT_BASE_URLS.get(provider)

    api_key = business.ai_api_key
    if not api_key:
        # Fall back to the env var that matches THIS provider's SDK family —
        # never cross-wire (passing OPENAI_API_KEY to Anthropic would 401).
        api_key = (
            settings.ANTHROPIC_API_KEY if sdk == "anthropic"
            else settings.OPENAI_API_KEY
        )

    return {
        "provider": provider,
        "sdk": sdk,
        "model": business.ai_model or settings.AI_MODEL,
        "api_key": api_key or "",
        "base_url": base_url,
        "input_price_per_million": (
            business.ai_input_price_per_million
            if business.ai_input_price_per_million is not None
            else settings.AI_PRICE_INPUT_PER_MILLION
        ),
        "output_price_per_million": (
            business.ai_output_price_per_million
            if business.ai_output_price_per_million is not None
            else settings.AI_PRICE_OUTPUT_PER_MILLION
        ),
    }


def compute_cost_usd(tokens_in: int, tokens_out: int, business: Business | None = None) -> float:
    """Unit-aware cost calculator. Uses the business' per-million prices if
    configured; otherwise falls back to the global env defaults.
    """
    if business is not None:
        cfg = _resolve_ai_config(business)
        input_p = cfg["input_price_per_million"]
        output_p = cfg["output_price_per_million"]
    else:
        input_p = settings.AI_PRICE_INPUT_PER_MILLION
        output_p = settings.AI_PRICE_OUTPUT_PER_MILLION
    cost_in = (tokens_in / 1_000_000) * input_p
    cost_out = (tokens_out / 1_000_000) * output_p
    return round(cost_in + cost_out, 4)


# ── Localized business fields (used by the system prompt) ─────────────────


def _get_localized_fields(db: Session, business: Business, language: str) -> dict:
    """Resolve business fields in `language`, falling back to the base Business
    columns per field when a translated value is empty.
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
        "phone": business.phone or "",
        "email": business.email or "",
    }


def _build_system_prompt(fields: dict, language: str) -> str:
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
- LANGUAGE: Reply in the SAME language the user writes in. If the user's message is ambiguous, very short, or mixes languages, default to {language_name} (the language currently selected in the chat widget). Never force {language_name} when the user is clearly writing in another language. If the user switches language mid-conversation, follow along — each reply matches the language of the most recent user message.
- Be concise: max 2-3 sentences per reply unless more detail is required.
"""


def _build_messages(conversation_history: list[Message], user_message: str) -> list[dict]:
    messages = []
    for msg in conversation_history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


# ── Client factories (take explicit credentials) ──────────────────────────


def _make_openai_client(api_key: str, base_url: str | None) -> openai.AsyncOpenAI:
    kwargs: dict = {"api_key": api_key or ""}
    if base_url:
        kwargs["base_url"] = base_url
    return openai.AsyncOpenAI(**kwargs)


def _make_anthropic_client(api_key: str, base_url: str | None) -> anthropic.AsyncAnthropic:
    kwargs: dict = {"api_key": api_key or ""}
    if base_url:
        kwargs["base_url"] = base_url
    return anthropic.AsyncAnthropic(**kwargs)


# ── High-level calls ──────────────────────────────────────────────────────


class AIError(Exception):
    """Raised when the AI provider fails. Callers log + fall back."""


def ai_fallback_message(business: Business) -> str:
    return (
        f"Lo siento, no puedo responder a eso ahora mismo. "
        f"Puedes contactarnos en {business.phone} o {business.email}."
    )


async def _openai_chat(config: dict, system: str, messages: list[dict], max_tokens: int = 500):
    client = _make_openai_client(config["api_key"], config["base_url"])
    resp = await client.chat.completions.create(
        model=config["model"],
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}] + messages,
    )
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    return text, (usage.prompt_tokens if usage else None), (usage.completion_tokens if usage else None)


async def _anthropic_chat(config: dict, system: str, messages: list[dict], max_tokens: int = 500):
    client = _make_anthropic_client(config["api_key"], config["base_url"])
    resp = await client.messages.create(
        model=config["model"],
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    text = resp.content[0].text
    usage = getattr(resp, "usage", None)
    return text, (usage.input_tokens if usage else None), (usage.output_tokens if usage else None)


async def generate_ai_response(
    business: Business,
    db: Session,
    conversation_history: list[Message],
    user_message: str,
    language: str = "es",
):
    fields = _get_localized_fields(db, business, language)
    system_prompt = _build_system_prompt(fields, language)
    messages = _build_messages(conversation_history, user_message)
    config = _resolve_ai_config(business)

    try:
        if config["sdk"] == "openai":
            return await _openai_chat(config, system_prompt, messages)
        return await _anthropic_chat(config, system_prompt, messages)
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
    fields = _get_localized_fields(db, business, language)
    system_prompt = _build_system_prompt(fields, language)
    messages = _build_messages(conversation_history, user_message)
    config = _resolve_ai_config(business)

    try:
        if config["sdk"] == "openai":
            client = _make_openai_client(config["api_key"], config["base_url"])
            stream = await client.chat.completions.create(
                model=config["model"],
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
            client = _make_anthropic_client(config["api_key"], config["base_url"])
            async with client.messages.stream(
                model=config["model"],
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


# ── JSON helper used by translation services ──────────────────────────────


async def chat_json(
    system: str,
    user: str,
    max_tokens: int = 2000,
    business: Business | None = None,
) -> str:
    """One-shot JSON-returning call. If a business is provided, uses its
    configured AI; otherwise uses the global env.
    """
    if business is not None:
        cfg = _resolve_ai_config(business)
    else:
        cfg = {
            "sdk": "anthropic" if (settings.AI_PROVIDER or "openai").lower() == "anthropic" else "openai",
            "model": settings.AI_MODEL,
            "api_key": settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY or "",
            "base_url": settings.OPENAI_BASE_URL or settings.ANTHROPIC_BASE_URL or None,
        }

    if cfg["sdk"] == "openai":
        client = _make_openai_client(cfg["api_key"], cfg["base_url"])
        resp = await client.chat.completions.create(
            model=cfg["model"],
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""
    client = _make_anthropic_client(cfg["api_key"], cfg["base_url"])
    resp = await client.messages.create(
        model=cfg["model"],
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text
