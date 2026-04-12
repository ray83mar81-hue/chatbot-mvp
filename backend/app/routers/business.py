import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.business import Business
from app.models.business_translation import BusinessTranslation
from app.models.language import Language
from app.schemas.business import BusinessCreate, BusinessResponse, BusinessUpdate
from app.schemas.business_translation import (
    BusinessTranslationResponse,
    BusinessTranslationUpdate,
    TranslateBusinessRequest,
)
from app.services.business_translation_service import translate_business
from app.services.translation_service import TranslationError

router = APIRouter(prefix="/business", tags=["business"])


@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(business_id: int, db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


@router.post("/", response_model=BusinessResponse)
def create_business(data: BusinessCreate, db: Session = Depends(get_db)):
    business = Business(**data.model_dump())
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


@router.put("/{business_id}", response_model=BusinessResponse)
def update_business(
    business_id: int, data: BusinessUpdate, db: Session = Depends(get_db)
):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(business, key, value)

    db.commit()
    db.refresh(business)
    return business


# ── Business translations ────────────────────────────────────────────


@router.get(
    "/{business_id}/translations",
    response_model=list[BusinessTranslationResponse],
)
def list_business_translations(business_id: int, db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return (
        db.query(BusinessTranslation)
        .filter(BusinessTranslation.business_id == business_id)
        .order_by(BusinessTranslation.language_code)
        .all()
    )


@router.put(
    "/{business_id}/translations/{language_code}",
    response_model=BusinessTranslationResponse,
)
def upsert_business_translation(
    business_id: int,
    language_code: str,
    data: BusinessTranslationUpdate,
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    lang = db.query(Language).filter(
        Language.code == language_code, Language.is_active.is_(True)
    ).first()
    if not lang:
        raise HTTPException(status_code=404, detail=f"Language '{language_code}' not found")

    update_data = data.model_dump(exclude_unset=True)

    translation = (
        db.query(BusinessTranslation)
        .filter_by(business_id=business_id, language_code=language_code)
        .first()
    )

    if translation:
        for key, value in update_data.items():
            setattr(translation, key, value)
        if any(k in update_data for k in ("name", "description", "address", "schedule", "extra_info")):
            translation.auto_translated = False
    else:
        translation = BusinessTranslation(
            business_id=business_id,
            language_code=language_code,
            name=update_data.get("name") or "",
            description=update_data.get("description") or "",
            address=update_data.get("address") or "",
            schedule=update_data.get("schedule") or "{}",
            extra_info=update_data.get("extra_info") or "",
            welcome=update_data.get("welcome") or "",
            privacy_url=update_data.get("privacy_url") or "",
            contact_texts=update_data.get("contact_texts") or "{}",
            auto_translated=False,
            needs_review=update_data.get("needs_review", False),
        )
        db.add(translation)

    db.commit()
    db.refresh(translation)
    return translation


@router.post(
    "/{business_id}/translate",
    response_model=list[BusinessTranslationResponse],
)
async def translate_business_endpoint(
    business_id: int,
    request: TranslateBusinessRequest = TranslateBusinessRequest(),
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    source_lang = request.source_language or business.default_language or "es"

    if request.target_languages is not None:
        targets = request.target_languages
    else:
        try:
            targets = json.loads(business.supported_languages or '["es"]')
        except json.JSONDecodeError:
            targets = ["es"]
        targets = [c for c in targets if c != source_lang]

    if not targets:
        raise HTTPException(status_code=400, detail="No target languages to translate into")

    try:
        results = await translate_business(
            business=business,
            source_language_code=source_lang,
            target_language_codes=targets,
            db=db,
            overwrite_reviewed=request.overwrite_reviewed,
        )
    except TranslationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return results
