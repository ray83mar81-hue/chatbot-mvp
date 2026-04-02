from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import ConversationListResponse, ConversationResponse

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
