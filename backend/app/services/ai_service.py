import json

import anthropic

from app.config import settings
from app.models.business import Business
from app.models.message import Message


def _build_system_prompt(business: Business) -> str:
    """Build a system prompt with the business context."""
    schedule = business.schedule or "{}"
    try:
        schedule_formatted = json.dumps(json.loads(schedule), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        schedule_formatted = schedule

    return f"""Eres el asistente virtual de "{business.name}". Tu rol es ayudar a los clientes
con sus preguntas de manera amable, profesional y concisa.

Información del negocio:
- Nombre: {business.name}
- Descripción: {business.description}
- Dirección: {business.address}
- Teléfono: {business.phone}
- Email: {business.email}
- Horarios: {schedule_formatted}

Información adicional:
{business.extra_info}

Reglas:
- Responde SOLO con información del negocio. No inventes datos.
- Si no tienes la información para responder, indica amablemente que no dispones de esa información y sugiere contactar directamente al negocio.
- Responde en el mismo idioma que el usuario.
- Sé conciso: máximo 2-3 oraciones por respuesta a menos que se requiera más detalle.
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
) -> str:
    """Generate a response using Claude API (direct or via OpenRouter)."""
    client = _get_client()
    system_prompt = _build_system_prompt(business)
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
):
    """Yield text chunks from Claude API stream."""
    client = _get_client()
    system_prompt = _build_system_prompt(business)
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
