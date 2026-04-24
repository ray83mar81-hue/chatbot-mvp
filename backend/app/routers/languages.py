"""Endpoints for the language catalog and per-business language settings."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import assert_business_write, get_current_user
from app.models.admin_user import AdminUser
from app.models.business import Business
from app.models.language import Language
from app.schemas.language import (
    BusinessLanguagesResponse,
    BusinessLanguagesUpdate,
    LanguageResponse,
)
from app.services.ai_service import ALLOWED_LANGUAGE_CODES

router = APIRouter(tags=["languages"])


@router.get("/languages/", response_model=list[LanguageResponse])
def list_languages(active_only: bool = True, db: Session = Depends(get_db)):
    """List the global language catalog."""
    query = db.query(Language)
    if active_only:
        query = query.filter(Language.is_active.is_(True))
    return query.order_by(Language.sort_order, Language.code).all()


@router.get(
    "/business/{business_id}/languages",
    response_model=BusinessLanguagesResponse,
)
def get_business_languages(business_id: int, db: Session = Depends(get_db)):
    """
    PUBLIC endpoint — used by the widget on init to know which languages to
    offer in the selector and what welcome message to show in each.
    """
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    try:
        codes = json.loads(business.supported_languages or '["es"]')
        if not isinstance(codes, list):
            codes = ["es"]
    except json.JSONDecodeError:
        codes = ["es"]

    try:
        welcomes = json.loads(business.welcome_messages or "{}")
        if not isinstance(welcomes, dict):
            welcomes = {}
    except json.JSONDecodeError:
        welcomes = {}

    try:
        ui_texts = json.loads(business.widget_ui_texts or "{}")
        if not isinstance(ui_texts, dict):
            ui_texts = {}
    except json.JSONDecodeError:
        ui_texts = {}

    try:
        design = json.loads(business.widget_design or "{}")
        if not isinstance(design, dict):
            design = {}
    except json.JSONDecodeError:
        design = {}

    languages = (
        db.query(Language)
        .filter(Language.code.in_(codes), Language.is_active.is_(True))
        .order_by(Language.sort_order, Language.code)
        .all()
    )

    # Preserve the order the admin defined in supported_languages
    by_code = {lang.code: lang for lang in languages}
    ordered = [by_code[c] for c in codes if c in by_code]

    return BusinessLanguagesResponse(
        business_id=business.id,
        default_language=business.default_language or "es",
        supported=ordered,
        welcome_messages=welcomes,
        widget_ui_texts=ui_texts,
        widget_design=design,
    )


@router.put(
    "/business/{business_id}/languages",
    response_model=BusinessLanguagesResponse,
)
def update_business_languages(
    business_id: int,
    data: BusinessLanguagesUpdate,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin: update which languages this business supports."""
    assert_business_write(current, business_id)
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    if data.supported_languages is not None:
        if not data.supported_languages:
            raise HTTPException(
                status_code=422,
                detail="At least one supported language is required",
            )
        # Two-layer validation: the code must be in the hardcoded allow-list
        # (product decision — chatbot quality is tested on those 7) AND it
        # must exist as an active row in the language catalog.
        not_allowed = [
            c for c in data.supported_languages
            if c not in ALLOWED_LANGUAGE_CODES
        ]
        if not_allowed:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Language code(s) not supported by the platform: {not_allowed}. "
                    f"Allowed codes: {sorted(ALLOWED_LANGUAGE_CODES)}."
                ),
            )
        catalog_codes = {
            row[0]
            for row in db.query(Language.code)
            .filter(Language.is_active.is_(True))
            .all()
        }
        missing = [c for c in data.supported_languages if c not in catalog_codes]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Language code(s) not in the active catalog: {missing}",
            )
        business.supported_languages = json.dumps(data.supported_languages)

    if data.default_language is not None:
        # Default must be in the supported list
        try:
            current_supported = json.loads(business.supported_languages or '["es"]')
        except json.JSONDecodeError:
            current_supported = ["es"]
        if data.default_language not in current_supported:
            raise HTTPException(
                status_code=422,
                detail=f"default_language '{data.default_language}' must be in supported_languages {current_supported}",
            )
        business.default_language = data.default_language

    if data.welcome_messages is not None:
        business.welcome_messages = json.dumps(data.welcome_messages, ensure_ascii=False)

    if data.widget_ui_texts is not None:
        ui_dict = {k: v.model_dump() for k, v in data.widget_ui_texts.items()}
        business.widget_ui_texts = json.dumps(ui_dict, ensure_ascii=False)

    if data.widget_design is not None:
        business.widget_design = json.dumps(data.widget_design.model_dump(), ensure_ascii=False)

    db.commit()
    db.refresh(business)

    # Re-use the GET response builder by calling it inline
    return get_business_languages(business_id, db)
