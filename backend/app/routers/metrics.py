from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.config import settings
from app.database import get_db
from app.deps import assert_business_access, get_current_user
from app.models.admin_user import AdminUser
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.metrics import DailyCount, MetricsResponse, TopIntent
from app.services.chat_limits import tokens_used_this_month

router = APIRouter(prefix="/metrics", tags=["metrics"])


class UsageResponse(BaseModel):
    business_id: int
    month_start: str
    tokens_used: int
    tokens_quota: int | None = None  # None = unlimited
    cost_usd: float
    ai_messages: int
    intent_messages: int
    total_bot_messages: int
    intent_ratio: float  # 0..1 — how many bot replies were served by intents (cheap)


@router.get("/usage", response_model=UsageResponse)
def get_usage(
    business_id: int = 1,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Current-month consumption for a tenant. Client sees their own business;
    superadmin can query any business_id.
    """
    assert_business_access(current, business_id)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    tokens_used = tokens_used_this_month(db, business_id)

    tokens_in_total = (
        db.query(func.coalesce(func.sum(Message.tokens_in), 0))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Conversation.business_id == business_id,
            Message.created_at >= month_start,
        )
        .scalar()
    ) or 0
    tokens_out_total = (
        db.query(func.coalesce(func.sum(Message.tokens_out), 0))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Conversation.business_id == business_id,
            Message.created_at >= month_start,
        )
        .scalar()
    ) or 0
    cost = round(
        (int(tokens_in_total) / 1_000_000) * settings.AI_PRICE_INPUT_PER_MILLION
        + (int(tokens_out_total) / 1_000_000) * settings.AI_PRICE_OUTPUT_PER_MILLION,
        4,
    )

    ai_msgs = (
        db.query(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Conversation.business_id == business_id,
            Message.role == "assistant",
            Message.source == "ai",
            Message.created_at >= month_start,
        )
        .scalar()
    ) or 0
    intent_msgs = (
        db.query(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Conversation.business_id == business_id,
            Message.role == "assistant",
            Message.source == "intent",
            Message.created_at >= month_start,
        )
        .scalar()
    ) or 0
    total_bot = ai_msgs + intent_msgs
    ratio = round(intent_msgs / total_bot, 2) if total_bot else 0.0

    return UsageResponse(
        business_id=business_id,
        month_start=month_start.isoformat(),
        tokens_used=tokens_used,
        tokens_quota=business.monthly_token_quota,
        cost_usd=cost,
        ai_messages=ai_msgs,
        intent_messages=intent_msgs,
        total_bot_messages=total_bot,
        intent_ratio=ratio,
    )


@router.get("/", response_model=MetricsResponse)
def get_metrics(
    business_id: int = 1,
    days: int = 30,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_access(current, business_id)
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
