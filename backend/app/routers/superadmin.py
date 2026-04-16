"""Superadmin-only endpoints: tenant (business) management + usage stats.

Every endpoint in this router requires role=superadmin.
"""
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import require_superadmin
from app.models.admin_user import AdminUser
from app.models.business import Business
from app.models.contact_request import ContactRequest
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.chat_limits import tokens_used_this_month

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


# ── Schemas ──────────────────────────────────────────────────────────


class BusinessStats(BaseModel):
    id: int
    name: str
    is_active: bool
    default_language: str
    created_at: datetime
    last_activity: datetime | None = None
    conversations_count: int
    messages_count: int
    tokens_in: int
    tokens_out: int
    tokens_this_month: int = 0
    monthly_token_quota: int | None = None
    cost_usd: float  # estimated
    contact_requests_count: int
    admin_emails: list[str]


class CreateTenantRequest(BaseModel):
    name: str
    admin_email: str
    admin_password: str
    default_language: str = "es"


class UpdateTenantRequest(BaseModel):
    is_active: bool | None = None
    name: str | None = None
    monthly_token_quota: int | None = None  # 0 or negative = clear quota (unlimited)


class PricingResponse(BaseModel):
    ai_model: str
    ai_provider: str
    input_per_million_usd: float
    output_per_million_usd: float


# ── Helpers ──────────────────────────────────────────────────────────


def _compute_cost_usd(tokens_in: int, tokens_out: int) -> float:
    cost_in = (tokens_in / 1_000_000) * settings.AI_PRICE_INPUT_PER_MILLION
    cost_out = (tokens_out / 1_000_000) * settings.AI_PRICE_OUTPUT_PER_MILLION
    return round(cost_in + cost_out, 4)


def _stats_for(business: Business, db: Session) -> BusinessStats:
    """Aggregate per-tenant usage. Hits several small queries (acceptable for
    a dashboard that loads once). If the tenant count grows past ~100, batch
    these into a single CTE query."""
    conv_count = (
        db.query(func.count(Conversation.id))
        .filter(Conversation.business_id == business.id)
        .scalar()
    ) or 0

    msg_count = (
        db.query(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.business_id == business.id, Message.role == "assistant")
        .scalar()
    ) or 0

    tokens_in = (
        db.query(func.coalesce(func.sum(Message.tokens_in), 0))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.business_id == business.id)
        .scalar()
    ) or 0
    tokens_out = (
        db.query(func.coalesce(func.sum(Message.tokens_out), 0))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.business_id == business.id)
        .scalar()
    ) or 0

    last_activity = (
        db.query(func.max(Message.created_at))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.business_id == business.id)
        .scalar()
    )

    contact_count = (
        db.query(func.count(ContactRequest.id))
        .filter(ContactRequest.business_id == business.id)
        .scalar()
    ) or 0

    admin_emails = [
        email for (email,) in db.query(AdminUser.email)
        .filter(AdminUser.business_id == business.id)
        .all()
    ]

    tokens_this_month = tokens_used_this_month(db, business.id)

    return BusinessStats(
        id=business.id,
        name=business.name,
        is_active=bool(business.is_active),
        default_language=business.default_language or "es",
        created_at=business.created_at,
        last_activity=last_activity,
        conversations_count=conv_count,
        messages_count=msg_count,
        tokens_in=int(tokens_in),
        tokens_out=int(tokens_out),
        tokens_this_month=tokens_this_month,
        monthly_token_quota=business.monthly_token_quota,
        cost_usd=_compute_cost_usd(int(tokens_in), int(tokens_out)),
        contact_requests_count=contact_count,
        admin_emails=admin_emails,
    )


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/pricing", response_model=PricingResponse)
def get_pricing(_: AdminUser = Depends(require_superadmin)):
    """Current AI model + unit prices used for cost calculations."""
    return PricingResponse(
        ai_model=settings.AI_MODEL,
        ai_provider=settings.AI_PROVIDER,
        input_per_million_usd=settings.AI_PRICE_INPUT_PER_MILLION,
        output_per_million_usd=settings.AI_PRICE_OUTPUT_PER_MILLION,
    )


@router.get("/businesses", response_model=list[BusinessStats])
def list_businesses(
    _: AdminUser = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    businesses = db.query(Business).order_by(Business.id).all()
    return [_stats_for(b, db) for b in businesses]


@router.get("/businesses/{business_id}", response_model=BusinessStats)
def get_business_stats(
    business_id: int,
    _: AdminUser = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return _stats_for(business, db)


@router.post("/businesses", response_model=BusinessStats, status_code=201)
def create_tenant(
    data: CreateTenantRequest,
    _: AdminUser = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    """Creates a new Business + the initial client_admin user in one step."""
    if not data.name.strip():
        raise HTTPException(status_code=422, detail="Name is required")
    if not data.admin_email.strip():
        raise HTTPException(status_code=422, detail="admin_email is required")
    if len(data.admin_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    existing_user = (
        db.query(AdminUser).filter(AdminUser.email == data.admin_email).first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    business = Business(
        name=data.name.strip(),
        description="",
        default_language=data.default_language,
        supported_languages=f'["{data.default_language}"]',
        is_active=True,
    )
    db.add(business)
    db.flush()  # get business.id

    admin = AdminUser(
        email=data.admin_email.strip(),
        password_hash=bcrypt.hashpw(data.admin_password.encode(), bcrypt.gensalt()).decode(),
        business_id=business.id,
        role="client_admin",
    )
    db.add(admin)
    db.commit()
    db.refresh(business)
    return _stats_for(business, db)


@router.patch("/businesses/{business_id}", response_model=BusinessStats)
def update_tenant(
    business_id: int,
    data: UpdateTenantRequest,
    _: AdminUser = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    if data.is_active is not None:
        business.is_active = data.is_active
    if data.name is not None and data.name.strip():
        business.name = data.name.strip()
    if data.monthly_token_quota is not None:
        # 0 or negative clears the quota (treat as unlimited)
        business.monthly_token_quota = (
            data.monthly_token_quota if data.monthly_token_quota > 0 else None
        )

    db.commit()
    db.refresh(business)
    return _stats_for(business, db)


@router.delete("/businesses/{business_id}", status_code=204)
def delete_tenant(
    business_id: int,
    _: AdminUser = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    """Hard-delete a business and its children. USE WITH CARE.
    Prefer PATCH is_active=false for soft suspension.
    """
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Detach any client_admin users tied to this business so they can be
    # re-used elsewhere. We don't delete admins because their email is unique
    # and deleting might surprise the operator.
    db.query(AdminUser).filter(AdminUser.business_id == business.id).update(
        {AdminUser.business_id: None}
    )
    db.delete(business)
    db.commit()
    return None


# ── Global metrics (across all tenants) ──────────────────────────────


class GlobalStats(BaseModel):
    total_businesses: int
    active_businesses: int
    total_conversations_30d: int
    total_messages_30d: int
    total_tokens_in_30d: int
    total_tokens_out_30d: int
    total_cost_usd_30d: float


@router.get("/stats", response_model=GlobalStats)
def global_stats(
    _: AdminUser = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=30)

    total_biz = db.query(func.count(Business.id)).scalar() or 0
    active_biz = (
        db.query(func.count(Business.id))
        .filter(Business.is_active.is_(True))
        .scalar()
    ) or 0

    conv_30d = (
        db.query(func.count(Conversation.id))
        .filter(Conversation.started_at >= since)
        .scalar()
    ) or 0
    msg_30d = (
        db.query(func.count(Message.id))
        .filter(Message.role == "assistant", Message.created_at >= since)
        .scalar()
    ) or 0
    tin_30d = (
        db.query(func.coalesce(func.sum(Message.tokens_in), 0))
        .filter(Message.created_at >= since)
        .scalar()
    ) or 0
    tout_30d = (
        db.query(func.coalesce(func.sum(Message.tokens_out), 0))
        .filter(Message.created_at >= since)
        .scalar()
    ) or 0

    return GlobalStats(
        total_businesses=total_biz,
        active_businesses=active_biz,
        total_conversations_30d=conv_30d,
        total_messages_30d=msg_30d,
        total_tokens_in_30d=int(tin_30d),
        total_tokens_out_30d=int(tout_30d),
        total_cost_usd_30d=_compute_cost_usd(int(tin_30d), int(tout_30d)),
    )
