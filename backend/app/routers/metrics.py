from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.metrics import DailyCount, MetricsResponse, TopIntent

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/", response_model=MetricsResponse)
def get_metrics(
    business_id: int = 1,
    days: int = 30,
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)

    # Total conversations
    total_conversations = (
        db.query(func.count(Conversation.id))
        .filter(
            Conversation.business_id == business_id,
            Conversation.started_at >= since,
        )
        .scalar()
    )

    # Total messages (assistant only, within date range)
    total_messages = (
        db.query(func.count(Message.id))
        .join(Conversation)
        .filter(
            Conversation.business_id == business_id,
            Message.role == "assistant",
            Message.created_at >= since,
        )
        .scalar()
    )

    # Messages by day
    daily_rows = (
        db.query(
            func.date(Message.created_at).label("day"),
            func.count(Message.id).label("count"),
        )
        .join(Conversation)
        .filter(
            Conversation.business_id == business_id,
            Message.role == "user",
            Message.created_at >= since,
        )
        .group_by(func.date(Message.created_at))
        .order_by(func.date(Message.created_at))
        .all()
    )
    messages_by_day = [DailyCount(date=str(r.day), count=r.count) for r in daily_rows]

    # Top matched intents
    intent_rows = (
        db.query(
            Message.intent_matched_id,
            func.count(Message.id).label("count"),
        )
        .join(Conversation)
        .filter(
            Conversation.business_id == business_id,
            Message.source == "intent",
            Message.intent_matched_id.isnot(None),
            Message.created_at >= since,
        )
        .group_by(Message.intent_matched_id)
        .order_by(func.count(Message.id).desc())
        .limit(10)
        .all()
    )

    from app.models.intent import Intent

    top_intents = []
    for row in intent_rows:
        intent = db.query(Intent).filter(Intent.id == row.intent_matched_id).first()
        if intent:
            top_intents.append(TopIntent(intent_name=intent.name, count=row.count))

    # AI fallback rate
    total_bot = (
        db.query(func.count(Message.id))
        .join(Conversation)
        .filter(
            Conversation.business_id == business_id,
            Message.role == "assistant",
            Message.created_at >= since,
        )
        .scalar()
    ) or 1  # Avoid division by zero
    ai_count = (
        db.query(func.count(Message.id))
        .join(Conversation)
        .filter(
            Conversation.business_id == business_id,
            Message.source == "ai",
            Message.created_at >= since,
        )
        .scalar()
    )
    ai_fallback_rate = round((ai_count / total_bot) * 100, 1)

    # Average response time
    avg_time = (
        db.query(func.avg(Message.response_time_ms))
        .join(Conversation)
        .filter(
            Conversation.business_id == business_id,
            Message.role == "assistant",
            Message.response_time_ms.isnot(None),
            Message.created_at >= since,
        )
        .scalar()
    ) or 0

    return MetricsResponse(
        total_conversations=total_conversations,
        total_messages=total_messages,
        messages_by_day=messages_by_day,
        top_intents=top_intents,
        ai_fallback_rate=ai_fallback_rate,
        avg_response_time_ms=round(avg_time, 1),
    )
