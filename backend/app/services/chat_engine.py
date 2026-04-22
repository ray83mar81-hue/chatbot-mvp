"""AI-only chat pipeline.

After the intent refactor, every customer message goes to the AI provider
with the localized business context. Action buttons (chips) live outside
this path — they're rendered by the widget on its own.
"""
import json as _json
import time

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_service import AIError, ai_fallback_message, generate_ai_response, stream_ai_response
from app.services.chat_limits import check_chat_gate
from app.services.incident_service import log as log_incident


def _resolve_language(request_lang: str | None, business: Business) -> str:
    if request_lang:
        return request_lang
    return business.default_language or "es"


def _get_or_create_conversation(
    db: Session, session_id: str, business_id: int, language: str = "es"
) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.session_id == session_id,
            Conversation.business_id == business_id,
            Conversation.status == "active",
        )
        .first()
    )
    if not conversation:
        conversation = Conversation(
            session_id=session_id,
            business_id=business_id,
            status="active",
            language_code=language,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    elif conversation.language_code != language:
        conversation.language_code = language
        db.commit()
    return conversation


async def process_message(request: ChatRequest, db: Session) -> ChatResponse:
    """Main chat pipeline: gate checks → persist user msg → AI reply → persist bot msg."""
    start_time = time.time()

    business = db.query(Business).filter(Business.id == request.business_id).first()
    if not business:
        return ChatResponse(
            response="Lo siento, no se encontró la configuración del negocio.",
            source="fallback",
            session_id=request.session_id,
            language=request.language or "es",
        )

    language = _resolve_language(request.language, business)

    gate = check_chat_gate(business, request.session_id, db, language)
    if not gate.ok:
        return ChatResponse(
            response=gate.message or "",
            source="fallback",
            session_id=request.session_id,
            language=language,
        )

    conversation = _get_or_create_conversation(
        db, request.session_id, request.business_id, language
    )

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    db.commit()

    history = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .all()
    )
    history = [m for m in history if m.id != user_msg.id]

    tokens_in: int | None = None
    tokens_out: int | None = None
    source = "ai"
    try:
        response_text, tokens_in, tokens_out = await generate_ai_response(
            business=business,
            db=db,
            conversation_history=history,
            user_message=request.message,
            language=language,
        )
    except AIError as err:
        log_incident(
            db, type="ai_error",
            message=f"Chat AI call failed for business {business.id}",
            business_id=business.id,
            details=str(err),
        )
        response_text = ai_fallback_message(business)
        source = "fallback"

    elapsed_ms = int((time.time() - start_time) * 1000)

    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        source=source,
        response_time_ms=elapsed_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    db.add(bot_msg)
    db.commit()

    return ChatResponse(
        response=response_text,
        source=source,
        session_id=request.session_id,
        language=language,
    )


async def process_message_stream(request: ChatRequest, db: Session):
    """SSE version. Emits start/chunk/end events."""
    business = db.query(Business).filter(Business.id == request.business_id).first()
    if not business:
        yield f"data: {_json.dumps({'type': 'error', 'content': 'Negocio no encontrado'})}\n\n"
        return

    language = _resolve_language(request.language, business)

    gate = check_chat_gate(business, request.session_id, db, language)
    if not gate.ok:
        yield f"data: {_json.dumps({'type': 'start', 'source': 'fallback', 'language': language})}\n\n"
        yield f"data: {_json.dumps({'type': 'chunk', 'content': gate.message or ''})}\n\n"
        yield f"data: {_json.dumps({'type': 'end'})}\n\n"
        return

    conversation = _get_or_create_conversation(db, request.session_id, request.business_id, language)

    user_msg = Message(conversation_id=conversation.id, role="user", content=request.message)
    db.add(user_msg)
    db.commit()

    history = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .all()
    )
    history = [m for m in history if m.id != user_msg.id]

    yield f"data: {_json.dumps({'type': 'start', 'source': 'ai', 'language': language})}\n\n"
    response_text = ""
    usage: dict = {}
    async for chunk in stream_ai_response(
        business=business,
        db=db,
        conversation_history=history,
        user_message=request.message,
        language=language,
        usage_out=usage,
    ):
        response_text += chunk
        yield f"data: {_json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
    yield f"data: {_json.dumps({'type': 'end'})}\n\n"

    source = "fallback" if usage.get("_error") else "ai"
    if usage.get("_error"):
        log_incident(
            db, type="ai_error",
            message=f"Streaming AI call failed for business {business.id}",
            business_id=business.id,
            details=usage["_error"],
        )

    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        source=source,
        response_time_ms=0,
        tokens_in=usage.get("tokens_in"),
        tokens_out=usage.get("tokens_out"),
    )
    db.add(bot_msg)
    db.commit()
