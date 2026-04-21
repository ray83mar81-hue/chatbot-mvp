"""Action buttons: fixed chips rendered in the widget header.

Replaces the old intent-based CTAs with a simpler model: a button is a
target (URL / phone / address) + a translated label, rendered unconditionally
as a chip. The widget shows all active buttons of a business; the AI chat
and the buttons are decoupled.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import assert_business_access, assert_business_write, get_current_user
from app.models.action_button import ACTION_BUTTON_TYPES, ActionButton
from app.models.action_button_translation import ActionButtonTranslation
from app.models.admin_user import AdminUser
from app.models.business import Business
from app.schemas.action_button import (
    ActionButtonAdmin,
    ActionButtonCreate,
    ActionButtonPublic,
    ActionButtonUpdate,
)

router = APIRouter(prefix="/business", tags=["action-buttons"])


def _validate_type(t: str) -> None:
    if t not in ACTION_BUTTON_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid type '{t}'. Valid: {', '.join(ACTION_BUTTON_TYPES)}",
        )


def _resolve_label(btn: ActionButton, lang: str, fallback_lang: str) -> str:
    by_lang = {t.language_code: t.label for t in btn.translations}
    return by_lang.get(lang) or by_lang.get(fallback_lang) or ""


# ── Public (widget) ──────────────────────────────────────────────────


@router.get(
    "/{business_id}/action-buttons",
    response_model=list[ActionButtonPublic],
)
def list_public(
    business_id: int,
    lang: str = Query("es"),
    db: Session = Depends(get_db),
):
    """Widget-facing list. Only active buttons, labels resolved to `lang`
    with fallback to the business default language. Supports `{lang}`
    placeholder in `value` (same convention as Intent.button_url).
    """
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    default_lang = business.default_language or "es"

    buttons = (
        db.query(ActionButton)
        .filter(
            ActionButton.business_id == business_id,
            ActionButton.is_active.is_(True),
        )
        .order_by(ActionButton.priority.desc(), ActionButton.id)
        .all()
    )
    return [
        ActionButtonPublic(
            id=b.id,
            type=b.type,
            value=(b.value or "").replace("{lang}", lang),
            icon=b.icon or "",
            label=_resolve_label(b, lang, default_lang),
            open_new_tab=bool(b.open_new_tab),
        )
        for b in buttons
    ]


# ── Admin ────────────────────────────────────────────────────────────


@router.get(
    "/{business_id}/action-buttons/admin",
    response_model=list[ActionButtonAdmin],
)
def list_admin(
    business_id: int,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_access(current, business_id)
    buttons = (
        db.query(ActionButton)
        .filter(ActionButton.business_id == business_id)
        .order_by(ActionButton.priority.desc(), ActionButton.id)
        .all()
    )
    return buttons


@router.post(
    "/{business_id}/action-buttons",
    response_model=ActionButtonAdmin,
    status_code=201,
)
def create_button(
    business_id: int,
    data: ActionButtonCreate,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_write(current, business_id)
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    _validate_type(data.type)

    btn = ActionButton(
        business_id=business_id,
        type=data.type,
        value=data.value or "",
        icon=data.icon or "",
        open_new_tab=data.open_new_tab,
        priority=data.priority,
        is_active=data.is_active,
    )
    db.add(btn)
    db.flush()

    for tr in data.translations or []:
        db.add(ActionButtonTranslation(
            action_button_id=btn.id,
            language_code=tr.language_code,
            label=tr.label or "",
        ))

    db.commit()
    db.refresh(btn)
    return btn


@router.patch(
    "/{business_id}/action-buttons/{button_id}",
    response_model=ActionButtonAdmin,
)
def update_button(
    business_id: int,
    button_id: int,
    data: ActionButtonUpdate,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_write(current, business_id)
    btn = (
        db.query(ActionButton)
        .filter(
            ActionButton.id == button_id,
            ActionButton.business_id == business_id,
        )
        .first()
    )
    if not btn:
        raise HTTPException(status_code=404, detail="Button not found")

    updates = data.model_dump(exclude_unset=True)
    translations = updates.pop("translations", None)

    if "type" in updates:
        _validate_type(updates["type"])
    for key, value in updates.items():
        setattr(btn, key, value)

    if translations is not None:
        # Replace the translation set (simpler than per-row merge; the admin
        # always sends the full set).
        db.query(ActionButtonTranslation).filter(
            ActionButtonTranslation.action_button_id == btn.id
        ).delete()
        for tr in translations:
            db.add(ActionButtonTranslation(
                action_button_id=btn.id,
                language_code=tr["language_code"],
                label=tr.get("label") or "",
            ))

    db.commit()
    db.refresh(btn)
    return btn


@router.delete(
    "/{business_id}/action-buttons/{button_id}",
    status_code=204,
)
def delete_button(
    business_id: int,
    button_id: int,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_write(current, business_id)
    btn = (
        db.query(ActionButton)
        .filter(
            ActionButton.id == button_id,
            ActionButton.business_id == business_id,
        )
        .first()
    )
    if not btn:
        raise HTTPException(status_code=404, detail="Button not found")
    db.delete(btn)
    db.commit()
    return None
