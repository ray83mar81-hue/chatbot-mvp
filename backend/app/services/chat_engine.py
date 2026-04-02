import time

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_service import generate_ai_response
from app.services.intent_matcher import match_intent


def _get_or_create_conversation(
    db: Session, session_id: str, business_id: int
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
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


async def process_message(request: ChatRequest, db: Session) -> ChatResponse:
    """
    Main chat pipeline:
    1. Get/create conversation
    2. Save user message
    3. Try intent matching
    4. If no match → AI fallback
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
        )

    # Get or create conversation
    conversation = _get_or_create_conversation(
        db, request.session_id, request.business_id
    )

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    db.commit()

    # Try intent matching first
    matched_intent = match_intent(request.message, db, request.business_id)

    if matched_intent:
        response_text = matched_intent.response
        source = "intent"
        intent_name = matched_intent.name
        intent_id = matched_intent.id
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

        response_text = await generate_ai_response(
            business=business,
            conversation_history=history,
            user_message=request.message,
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
    )
    db.add(bot_msg)
    db.commit()

    return ChatResponse(
        response=response_text,
        source=source,
        session_id=request.session_id,
        intent_name=intent_name,
    )
