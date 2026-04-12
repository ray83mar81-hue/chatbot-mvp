import json

import anthropic

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


def _get_client() -> anthropic.AsyncAnthropic:
    client_kwargs = {"api_key": settings.ANTHROPIC_API_KEY}
    if settings.ANTHROPIC_BASE_URL:
        client_kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
    return anthropic.AsyncAnthropic(**client_kwargs)


async def generate_ai_response(
    business: Business,
    conversation_history: list[Message],
    user_message: str,
    language: str = "es",
) -> str:
    """Generate a response using Claude API (direct or via OpenRouter)."""
    client = _get_client()
    system_prompt = _build_system_prompt(business, language)
    messages = _build_messages(conversation_history, user_message)

    try:
        response = await client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=500,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
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
):
    """Yield text chunks from Claude API stream."""
    client = _get_client()
    system_prompt = _build_system_prompt(business, language)
    messages = _build_messages(conversation_history, user_message)

    try:
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
