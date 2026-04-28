"""Per-language Frequently Asked Questions for a business.

FAQs live inside business_translations.faqs_json as a JSON array of
{q, a} pairs. They are:
  - editable from the admin Negocio → FAQs subtab via this router.
  - rendered as a collapsible accordion on the public landing page.
  - injected into the AI system prompt as a structured block so the
    chatbot uses them when answering customer questions.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import assert_business_access, assert_business_write, get_current_user
from app.models.admin_user import AdminUser
from app.models.business_translation import BusinessTranslation
from app.models.language import Language

router = APIRouter(prefix="/business", tags=["faqs"])


class FAQItem(BaseModel):
    q: str = Field(..., min_length=1, max_length=500)
    a: str = Field("", max_length=4000)


class FAQList(BaseModel):
    items: list[FAQItem] = []


@router.get("/{business_id}/faqs/{language_code}", response_model=FAQList)
def get_faqs(
    business_id: int,
    language_code: str,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read the FAQ list for one (business, language). Admin-only."""
    assert_business_access(current, business_id)

    tr = (
        db.query(BusinessTranslation)
        .filter(
            BusinessTranslation.business_id == business_id,
            BusinessTranslation.language_code == language_code,
        )
        .first()
    )
    if not tr:
        return FAQList(items=[])
    try:
        raw = json.loads(tr.faqs_json or "[]")
        if not isinstance(raw, list):
            raw = []
    except json.JSONDecodeError:
        raw = []
    items: list[FAQItem] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        q = str(entry.get("q") or "").strip()
        a = str(entry.get("a") or "").strip()
        if not q:
            continue
        items.append(FAQItem(q=q, a=a))
    return FAQList(items=items)


@router.put("/{business_id}/faqs/{language_code}", response_model=FAQList)
def save_faqs(
    business_id: int,
    language_code: str,
    payload: FAQList,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replace the FAQ list for one (business, language) atomically.

    Empty items (no question) are dropped silently. Order is preserved
    from the request — the admin UI controls reorder via up/down buttons.
    """
    assert_business_write(current, business_id)

    # Validate the language code exists in the catalog (active or not).
    lang = db.query(Language).filter(Language.code == language_code).first()
    if not lang:
        raise HTTPException(status_code=422, detail=f"Unknown language code: {language_code}")

    tr = (
        db.query(BusinessTranslation)
        .filter(
            BusinessTranslation.business_id == business_id,
            BusinessTranslation.language_code == language_code,
        )
        .first()
    )
    if not tr:
        # Auto-create a translation row so admins can edit FAQs without
        # going through "Datos del negocio" first.
        tr = BusinessTranslation(
            business_id=business_id,
            language_code=language_code,
        )
        db.add(tr)
        db.flush()

    # Normalize: drop blanks, trim, cap length.
    cleaned: list[dict] = []
    for item in payload.items:
        q = (item.q or "").strip()
        a = (item.a or "").strip()
        if not q:
            continue
        cleaned.append({"q": q, "a": a})

    tr.faqs_json = json.dumps(cleaned, ensure_ascii=False)
    db.commit()
    return FAQList(items=[FAQItem(**c) for c in cleaned])
