import json as _json
import time

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.conversation import Conversation
from app.models.intent import Intent
from app.models.intent_translation import IntentTranslation
from app.models.message import Message
from app.schemas.chat import ChatButton, ChatRequest, ChatResponse
from app.services.ai_service import generate_ai_response, stream_ai_response
from app.services.chat_limits import check_chat_gate
from app.services.intent_matcher import match_intent


def _resolve_language(request_lang: str | None, business: Business) -> str:
    """Pick the language to use for this turn."""
    if request_lang:
        return request_lang
    return business.default_language or "es"


def _build_button(
    intent: Intent, translation: IntentTranslation, language: str
) -> ChatButton | None:
    """
    Build a ChatButton from intent + translation, or None if no button is set.
    The URL supports a {lang} placeholder that gets replaced with the active
    language code (e.g. "https://web.com/{lang}/horarios" → ".../en/horarios").
    """
    url = (intent.button_url or "").strip()
    label = (translation.button_label or "").strip() if translation else ""
    if not url or not label:
        return None
    return ChatButton(
        label=label,
        url=url.replace("{lang}", language),
        open_new_tab=bool(intent.button_open_new_tab),
    )


def _get_or_create_conversation(
    db: Session, session_id: str, business_id: int, language: str = "es"
) -> Conversation:
    """Find existing active conversation or create a new one."""
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
        # User switched language mid-conversation — track the latest one
        conversation.language_code = language
        db.commit()
    return conversation


async def process_message(request: ChatRequest, db: Session) -> ChatResponse:
    """
    Main chat pipeline:
    1. Get/create conversation
    2. Save user message
    3. Try intent matching in the active language
    4. If no match → AI fallback (forced to respond in the active language)
    5. Save bot response
    6. Return response
    """
    start_time = time.time()

    # Verify business exists
    business = db.query(Business).filter(Business.id == request.business_id).first()
    if not business:
        return ChatResponse(
            response="Lo siento, no se encontró la configuración del negocio.",
            source="fallback",
            session_id=request.session_id,
            language=request.language or "es",
        )

    language = _resolve_language(request.language, business)

    # Gate: suspension, rate limit, monthly token quota
    gate = check_chat_gate(business, request.session_id, db, language)
    if not gate.ok:
        return ChatResponse(
            response=gate.message or "",
            source="fallback",
            session_id=request.session_id,
            language=language,
        )

    # Get or create conversation
    conversation = _get_or_create_conversation(
        db, request.session_id, request.business_id, language
    )

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    db.commit()

    # Try intent matching first (in the user's language)
    matched = match_intent(request.message, db, request.business_id, language)

    button: ChatButton | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    if matched:
        intent, translation = matched
        response_text = translation.response
        source = "intent"
        intent_name = intent.name
        intent_id = intent.id
        button = _build_button(intent, translation, language)
    else:
        # AI fallback — send conversation history for context
        history = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
            .all()
        )
        # Exclude the message we just saved (it goes in user_message param)
        history = [m for m in history if m.id != user_msg.id]

        response_text, tokens_in, tokens_out = await generate_ai_response(
            business=business,
            conversation_history=history,
            user_message=request.message,
            language=language,
        )
        source = "ai"
        intent_name = None
        intent_id = None

    elapsed_ms = int((time.time() - start_time) * 1000)

    # Save bot response
    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        source=source,
        intent_matched_id=intent_id,
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
        intent_name=intent_name,
        button=button,
    )


async def process_message_stream(request: ChatRequest, db: Session):
    """
    Streaming version of process_message.
    Yields SSE events:
      - {"type": "start", "source": "intent"|"ai", "language": "..."}
      - {"type": "chunk", "content": "..."}
      - {"type": "button", "label": "...", "url": "...", "open_new_tab": bool}  (only if intent has a button)
      - {"type": "end"}
    """
    business = db.query(Business).filter(Business.id == request.business_id).first()
    if not business:
        yield f"data: {_json.dumps({'type': 'error', 'content': 'Negocio no encontrado'})}\n\n"
        return

    language = _resolve_language(request.language, business)

    # Gate: suspension, rate limit, quota. Failure is surfaced as a synthetic
    # bot message so the widget renders it naturally.
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

    matched = match_intent(request.message, db, request.business_id, language)

    button: ChatButton | None = None
    if matched:
        intent, translation = matched
        response_text = translation.response
        button = _build_button(intent, translation, language)

        yield f"data: {_json.dumps({'type': 'start', 'source': 'intent', 'language': language})}\n\n"
        yield f"data: {_json.dumps({'type': 'chunk', 'content': response_text})}\n\n"
        if button:
            yield f"data: {_json.dumps({'type': 'button', 'label': button.label, 'url': button.url, 'open_new_tab': button.open_new_tab})}\n\n"
        yield f"data: {_json.dumps({'type': 'end'})}\n\n"
        source = "intent"
        intent_id = intent.id
    else:
        # AI stream
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
            conversation_history=history,
            user_message=request.message,
            language=language,
            usage_out=usage,
        ):
            response_text += chunk
            yield f"data: {_json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        yield f"data: {_json.dumps({'type': 'end'})}\n\n"
        source = "ai"
        intent_id = None
        _stream_tokens_in = usage.get("tokens_in")
        _stream_tokens_out = usage.get("tokens_out")

    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        source=source,
        intent_matched_id=intent_id,
        response_time_ms=0,
        tokens_in=locals().get("_stream_tokens_in"),
        tokens_out=locals().get("_stream_tokens_out"),
    )
    db.add(bot_msg)
    db.commit()
