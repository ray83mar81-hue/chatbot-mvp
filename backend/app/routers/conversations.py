import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.language import Language
from app.models.message import Message
from app.schemas.chat import (
    ConversationListResponse,
    ConversationResponse,
    TranslateConversationRequest,
    TranslateConversationResponse,
    TranslatedMessage,
)
from app.services.ai_service import _get_client
from app.services.translation_service import TranslationError, _extract_json

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/", response_model=list[ConversationListResponse])
def list_conversations(
    business_id: int = 1,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    conversations = (
        db.query(Conversation)
        .filter(Conversation.business_id == business_id)
        .order_by(Conversation.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for conv in conversations:
        msg_count = (
            db.query(func.count(Message.id))
            .filter(Message.conversation_id == conv.id)
            .scalar()
        )
        last_msg = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        results.append(
            ConversationListResponse(
                id=conv.id,
                session_id=conv.session_id,
                status=conv.status,
                language_code=conv.language_code or "es",
                started_at=conv.started_at,
                message_count=msg_count,
                last_message=last_msg.content if last_msg else None,
            )
        )
    return results


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post(
    "/{conversation_id}/translate",
    response_model=TranslateConversationResponse,
)
async def translate_conversation(
    conversation_id: int,
    data: TranslateConversationRequest = TranslateConversationRequest(),
    db: Session = Depends(get_db),
):
    """Translate every message of a conversation to a target language via AI.
    Result is returned on-the-fly (not persisted). Admin can translate the same
    conversation multiple times to different languages.
    """
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    business = db.query(Business).filter(Business.id == conversation.business_id).first()
    target_code = (data.target_language or (business.default_language if business else "es")).strip()
    source_code = conversation.language_code or "es"

    if source_code == target_code:
        # No translation needed — just return messages as-is
        return TranslateConversationResponse(
            conversation_id=conversation.id,
            source_language=source_code,
            target_language=target_code,
            messages=[
                TranslatedMessage(
                    id=m.id, role=m.role, content=m.content,
                    source=m.source, created_at=m.created_at,
                )
                for m in conversation.messages
            ],
        )

    # Resolve readable language names for the prompt
    langs = (
        db.query(Language)
        .filter(Language.code.in_([source_code, target_code]))
        .all()
    )
    names = {l.code: l.name for l in langs}
    source_name = names.get(source_code, source_code.upper())
    target_name = names.get(target_code, target_code.upper())

    messages = list(conversation.messages)
    if not messages:
        return TranslateConversationResponse(
            conversation_id=conversation.id,
            source_language=source_code,
            target_language=target_code,
            messages=[],
        )

    payload = [{"id": m.id, "role": m.role, "content": m.content} for m in messages]

    prompt = f"""Translate the following chat conversation messages from {source_name} into {target_name}.

Rules:
- Translate naturally and idiomatically, preserving tone.
- Keep URLs, phone numbers, emails and proper nouns unchanged.
- Do NOT add commentary or explanations.
- Preserve the exact message "id" in each output entry.
- Output ONLY a JSON object with this schema:

{{
  "messages": [
    {{ "id": <int>, "content": "<translated>" }}
  ]
}}

Input messages:
{json.dumps(payload, ensure_ascii=False)}
"""

    client = _get_client()
    try:
        response = await client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=4000,
            system="You are a professional translator. Reply with valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI translation failed: {type(e).__name__}: {e}",
        ) from e

    try:
        parsed = _extract_json(raw_text)
    except TranslationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    translated_by_id = {}
    for item in parsed.get("messages", []) or []:
        if isinstance(item, dict) and "id" in item and "content" in item:
            translated_by_id[int(item["id"])] = str(item["content"])

    result = []
    for m in messages:
        result.append(TranslatedMessage(
            id=m.id,
            role=m.role,
            content=translated_by_id.get(m.id, m.content),  # fallback: original
            source=m.source,
            created_at=m.created_at,
        ))

    return TranslateConversationResponse(
        conversation_id=conversation.id,
        source_language=source_code,
        target_language=target_code,
        messages=result,
    )
