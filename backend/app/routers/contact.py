"""Endpoints for the contact form and contact request management."""
import hashlib
import re
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import assert_business_access, assert_business_write, get_current_user
from app.models.admin_user import AdminUser
from app.models.business import Business
from app.models.business_translation import BusinessTranslation
from app.models.contact_request import ContactRequest
from app.models.conversation import Conversation
from app.schemas.contact import (
    ContactConfigResponse,
    ContactRequestResponse,
    ContactRequestUpdate,
    ContactSubmit,
)
from app.services.incident_service import log as log_incident
from app.services.notification_service import send_contact_notification

router = APIRouter(tags=["contact"])

# ── Simple in-memory rate limiter (per session_id) ──────────────────
# Tracks timestamps of recent submits. Max 3 per session in a 1-hour window.
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_MAX = 3
RATE_WINDOW = 3600  # 1 hour in seconds


def _rate_ok(session_id: str) -> bool:
    now = time.time()
    timestamps = _rate_store[session_id]
    # Prune old entries
    _rate_store[session_id] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(_rate_store[session_id]) >= RATE_MAX:
        return False
    _rate_store[session_id].append(now)
    return True


def _hash_ip(ip: str) -> str:
    """One-way hash of the IP with a server-side salt. GDPR-safe."""
    raw = f"{settings.IP_HASH_SALT}:{ip}".encode()
    return hashlib.sha256(raw).hexdigest()


def _validate_phone(phone: str) -> bool:
    """Basic phone validation: at least 6 digits after stripping non-digits."""
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 6


# ── Public endpoints ─────────────────────────────────────────────────


@router.get(
    "/business/{business_id}/contact-config",
    response_model=ContactConfigResponse,
)
def get_contact_config(business_id: int, db: Session = Depends(get_db)):
    """Public endpoint — the widget calls this to know if the form is enabled."""
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    # Build per-language translations for the contact form
    biz_translations = (
        db.query(BusinessTranslation)
        .filter(BusinessTranslation.business_id == business_id)
        .all()
    )
    translations = {}
    for bt in biz_translations:
        entry = {}
        if bt.privacy_url:
            entry["privacy_url"] = bt.privacy_url
        if bt.contact_texts:
            try:
                import json as _json
                texts = _json.loads(bt.contact_texts)
                if isinstance(texts, dict):
                    entry.update(texts)
            except Exception:
                pass
        if entry:
            translations[bt.language_code] = entry

    return ContactConfigResponse(
        contact_form_enabled=bool(business.contact_form_enabled),
        whatsapp_enabled=bool(business.whatsapp_enabled),
        privacy_url=business.privacy_url or "",
        translations=translations,
    )


@router.post("/contact/submit", response_model=ContactRequestResponse)
def submit_contact(
    data: ContactSubmit,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Public endpoint — receives the contact form submission from the widget.

    Anti-spam: honeypot field must be empty. Rate-limited per session_id.
    Saves to DB and sends email notification (if SMTP configured).
    """
    # Honeypot: if filled → silently accept but don't save (bots won't notice)
    if data.honeypot:
        # Return a fake response so the bot thinks it worked
        return ContactRequestResponse(
            id=0,
            business_id=data.business_id,
            conversation_id=None,
            name=data.name,
            phone=data.phone,
            email=data.email,
            message=data.message,
            whatsapp_opt_in=data.whatsapp_opt_in,
            privacy_accepted=data.privacy_accepted,
            language=data.language,
            status="new",
            notes="",
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )

    # Rate limit
    if data.session_id and not _rate_ok(data.session_id):
        raise HTTPException(
            status_code=429,
            detail="Too many contact requests. Please try again later.",
        )

    # Validate required fields
    if not data.name.strip():
        raise HTTPException(status_code=422, detail="Name is required")
    if not _validate_phone(data.phone):
        raise HTTPException(status_code=422, detail="Invalid phone number")
    if not data.message.strip():
        raise HTTPException(status_code=422, detail="Message is required")
    if not data.privacy_accepted:
        raise HTTPException(
            status_code=422,
            detail="Privacy policy must be accepted",
        )

    # Verify business exists and contact form is enabled
    business = db.query(Business).filter(Business.id == data.business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    if not business.contact_form_enabled:
        raise HTTPException(status_code=403, detail="Contact form is disabled")

    # Try to link to an existing conversation
    conversation_id = None
    if data.session_id:
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.session_id == data.session_id,
                Conversation.business_id == data.business_id,
            )
            .first()
        )
        if conv:
            conversation_id = conv.id

    # Hash the client IP
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = _hash_ip(client_ip)
    user_agent = (request.headers.get("user-agent") or "")[:500]

    contact = ContactRequest(
        business_id=data.business_id,
        conversation_id=conversation_id,
        name=data.name.strip(),
        phone=data.phone.strip(),
        email=data.email.strip(),
        message=data.message.strip(),
        whatsapp_opt_in=data.whatsapp_opt_in,
        privacy_accepted=True,
        privacy_accepted_at=datetime.now(timezone.utc),
        language=data.language,
        user_agent=user_agent,
        ip_hash=ip_hash,
        status="new",
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    # Send email notification (best-effort — don't fail the request if it errors)
    try:
        send_contact_notification(contact, business)
    except Exception as e:
        print(f"[Contact notification error] {type(e).__name__}: {e}")
        log_incident(
            db, type="email_failed",
            message=f"No se pudo enviar el email de notificación del contacto #{contact.id}",
            business_id=business.id,
            details=f"{type(e).__name__}: {e}",
        )

    return contact


# ── Admin endpoints ──────────────────────────────────────────────────


@router.get(
    "/contact/requests",
    response_model=list[ContactRequestResponse],
)
def list_contact_requests(
    business_id: int = 1,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List contact requests for a business, optionally filtered by status."""
    assert_business_access(current, business_id)
    query = db.query(ContactRequest).filter(
        ContactRequest.business_id == business_id,
    )
    if status:
        query = query.filter(ContactRequest.status == status)
    return (
        query.order_by(ContactRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/contact/requests/{contact_id}",
    response_model=ContactRequestResponse,
)
def get_contact_request(
    contact_id: int,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = (
        db.query(ContactRequest).filter(ContactRequest.id == contact_id).first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact request not found")
    assert_business_access(current, contact.business_id)
    return contact


@router.put(
    "/contact/requests/{contact_id}",
    response_model=ContactRequestResponse,
)
def update_contact_request(
    contact_id: int,
    data: ContactRequestUpdate,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update status (new → contacted → closed) or add admin notes."""
    contact = (
        db.query(ContactRequest).filter(ContactRequest.id == contact_id).first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact request not found")
    assert_business_write(current, contact.business_id)

    if data.status is not None:
        valid = {"new", "contacted", "closed"}
        if data.status not in valid:
            raise HTTPException(
                status_code=422, detail=f"Invalid status. Must be one of: {valid}"
            )
        contact.status = data.status

    if data.notes is not None:
        contact.notes = data.notes

    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/contact/requests/{contact_id}")
def delete_contact_request(
    contact_id: int,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GDPR: delete a contact request (right to erasure)."""
    contact = (
        db.query(ContactRequest).filter(ContactRequest.id == contact_id).first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact request not found")
    assert_business_write(current, contact.business_id)
    db.delete(contact)
    db.commit()
    return {"detail": "Contact request deleted"}
