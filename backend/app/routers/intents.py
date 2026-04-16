import csv
import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import assert_business_access, assert_business_write, get_current_user
from app.models.admin_user import AdminUser
from app.models.business import Business
from app.models.intent import Intent
from app.models.intent_translation import IntentTranslation
from app.models.language import Language
from app.schemas.intent import IntentCreate, IntentResponse, IntentUpdate
from app.schemas.intent_translation import (
    IntentTranslationResponse,
    IntentTranslationUpdate,
    TranslateIntentRequest,
    TranslateIntentResponse,
)
from app.services.translation_service import TranslationError, translate_intent

router = APIRouter(prefix="/intents", tags=["intents"])


def _get_intent_and_check_access(
    intent_id: int, current: AdminUser, db: Session
) -> Intent:
    intent = db.query(Intent).filter(Intent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")
    assert_business_access(current, intent.business_id)
    return intent


def _get_intent_and_check_write(
    intent_id: int, current: AdminUser, db: Session
) -> Intent:
    intent = db.query(Intent).filter(Intent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")
    assert_business_write(current, intent.business_id)
    return intent


CSV_TEMPLATE = (
    "name,keywords,response,priority,button_url,button_label\n"
    "horarios,\"horario,hora,abierto\",\"Abrimos de Lunes a Viernes de 7h a 20h. Sábados de 8h a 21h.\",10,,\n"
    "ubicacion,\"donde,ubicacion,direccion,mapa\",\"Estamos en Calle Mayor 42. Parking público a 2 min.\",10,,\n"
    "reservas,\"reservar,reserva,mesa,grupo\",\"Para grupos de 6+ personas, llama al +34 612 345 678.\",5,https://calendly.com/tunegocio,Reservar\n"
)


# Static routes must come BEFORE /{intent_id} so FastAPI doesn't try to
# interpret "template.csv" as an intent id.
@router.get("/template.csv", response_class=PlainTextResponse)
def download_template(_: AdminUser = Depends(get_current_user)):
    """Download a sample CSV template with 3 example intents."""
    return PlainTextResponse(
        content=CSV_TEMPLATE,
        headers={"Content-Disposition": 'attachment; filename="intents-template.csv"'},
        media_type="text/csv; charset=utf-8",
    )


@router.get("/", response_model=list[IntentResponse])
def list_intents(
    business_id: int = 1,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_access(current, business_id)
    return (
        db.query(Intent)
        .filter(Intent.business_id == business_id)
        .order_by(Intent.priority.desc())
        .all()
    )


@router.get("/{intent_id}", response_model=IntentResponse)
def get_intent(
    intent_id: int,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_intent_and_check_access(intent_id, current, db)


@router.post("/", response_model=IntentResponse)
def create_intent(
    data: IntentCreate,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_write(current, data.business_id)
    intent = Intent(**data.model_dump())
    db.add(intent)
    db.commit()
    db.refresh(intent)

    # Auto-seed a translation in the business default language so the matcher
    # can find this intent immediately. Other languages are added later via
    # the translate endpoint or manually.
    business = db.query(Business).filter(Business.id == intent.business_id).first()
    default_lang = (business.default_language if business else None) or "es"
    seed = IntentTranslation(
        intent_id=intent.id,
        language_code=default_lang,
        keywords=intent.keywords or "[]",
        response=intent.response or "",
        button_label="",
        auto_translated=False,
        needs_review=False,
    )
    db.add(seed)
    db.commit()

    return intent


@router.put("/{intent_id}", response_model=IntentResponse)
def update_intent(
    intent_id: int,
    data: IntentUpdate,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    intent = _get_intent_and_check_write(intent_id, current, db)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(intent, key, value)

    db.commit()
    db.refresh(intent)
    return intent


@router.delete("/{intent_id}")
def delete_intent(
    intent_id: int,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    intent = _get_intent_and_check_write(intent_id, current, db)
    db.delete(intent)
    db.commit()
    return {"detail": "Intent deleted"}


# ── Translations ────────────────────────────────────────────────────


@router.get(
    "/{intent_id}/translations",
    response_model=list[IntentTranslationResponse],
)
def list_intent_translations(
    intent_id: int,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all translations of an intent (one row per language)."""
    intent = _get_intent_and_check_access(intent_id, current, db)
    return (
        db.query(IntentTranslation)
        .filter(IntentTranslation.intent_id == intent_id)
        .order_by(IntentTranslation.language_code)
        .all()
    )


@router.put(
    "/{intent_id}/translations/{language_code}",
    response_model=IntentTranslationResponse,
)
def upsert_intent_translation(
    intent_id: int,
    language_code: str,
    data: IntentTranslationUpdate,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create or update a translation for this language (upsert).
    Setting needs_review=False marks it as human-reviewed (won't be overwritten
    by future auto-translations unless overwrite_reviewed=True).
    """
    intent = _get_intent_and_check_write(intent_id, current, db)

    # Verify the language exists and is active
    lang = (
        db.query(Language)
        .filter(Language.code == language_code, Language.is_active.is_(True))
        .first()
    )
    if not lang:
        raise HTTPException(
            status_code=404, detail=f"Language '{language_code}' not found"
        )

    update_data = data.model_dump(exclude_unset=True)

    # Validate keywords JSON if provided
    if "keywords" in update_data and update_data["keywords"] is not None:
        try:
            parsed = json.loads(update_data["keywords"])
            if not isinstance(parsed, list):
                raise ValueError("keywords must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=422, detail=f"Invalid keywords JSON: {e}"
            ) from e

    translation = (
        db.query(IntentTranslation)
        .filter(
            IntentTranslation.intent_id == intent_id,
            IntentTranslation.language_code == language_code,
        )
        .first()
    )

    if translation:
        for key, value in update_data.items():
            setattr(translation, key, value)
        # Manual edit → no longer auto-translated
        if any(k in update_data for k in ("keywords", "response", "button_label")):
            translation.auto_translated = False
    else:
        translation = IntentTranslation(
            intent_id=intent_id,
            language_code=language_code,
            keywords=update_data.get("keywords") or "[]",
            response=update_data.get("response") or "",
            button_label=update_data.get("button_label") or "",
            auto_translated=False,
            needs_review=update_data.get("needs_review", False),
        )
        db.add(translation)

    db.commit()
    db.refresh(translation)
    return translation


@router.post(
    "/{intent_id}/translate",
    response_model=TranslateIntentResponse,
)
async def translate_intent_endpoint(
    intent_id: int,
    request: TranslateIntentRequest = TranslateIntentRequest(),
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate AI translations for an intent.
    Defaults to translating into all the business's supported_languages
    minus the source language.
    Each call costs tokens — use sparingly. Generated translations are
    stored with needs_review=True so the admin can review them in the UI.
    """
    intent = _get_intent_and_check_write(intent_id, current, db)

    business = db.query(Business).filter(Business.id == intent.business_id).first()
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
        targets = [code for code in targets if code != source_lang]

    if not targets:
        raise HTTPException(
            status_code=400,
            detail="No target languages to translate into",
        )

    try:
        results = await translate_intent(
            intent=intent,
            source_language_code=source_lang,
            target_language_codes=targets,
            db=db,
            overwrite_reviewed=request.overwrite_reviewed,
        )
    except TranslationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return TranslateIntentResponse(
        intent_id=intent.id,
        source_language=source_lang,
        translations=results,
    )


# ── CSV bulk import ──────────────────────────────────────────────────


class ImportResult(BaseModel):
    created: int
    skipped: list[dict]    # [{name, reason}]
    errors: list[dict]     # [{row, reason}]


@router.post("/import", response_model=ImportResult)
async def import_intents_csv(
    business_id: int,
    file: UploadFile = File(...),
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk-create intents from a CSV file.

    Expected columns (header required): name, keywords, response, priority,
    button_url, button_label. Keywords comma-separated inside the cell.
    Intents are created in the business's default language.
    Duplicates (by intent name within this business) are skipped, not
    overwritten, to avoid accidental data loss.
    """
    assert_business_write(current, business_id)

    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    default_lang = business.default_language or "es"

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")  # strips BOM Excel loves to add
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="File must be UTF-8 or Latin-1 encoded")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV is empty")

    required = {"name", "response"}
    missing = required - set(h.strip().lower() for h in reader.fieldnames)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required columns: {', '.join(missing)}. Required: name, response.",
        )

    # Existing names in this business — de-dup source
    existing_names = {
        n for (n,) in db.query(Intent.name).filter(Intent.business_id == business_id).all()
    }

    created = 0
    skipped: list[dict] = []
    errors: list[dict] = []

    for idx, row in enumerate(reader, start=2):  # header is row 1
        # Normalise keys
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        name = row.get("name", "")
        response_text = row.get("response", "")
        if not name:
            errors.append({"row": idx, "reason": "name is empty"})
            continue
        if not response_text:
            errors.append({"row": idx, "reason": f"response is empty for '{name}'"})
            continue
        if name in existing_names:
            skipped.append({"name": name, "reason": "already exists"})
            continue

        try:
            priority = int(row.get("priority") or 10)
        except ValueError:
            priority = 10

        # Parse keywords: "horario, hora, abierto" → list
        kw_raw = row.get("keywords", "")
        kw_list = [k.strip() for k in kw_raw.split(",") if k.strip()]
        kw_json = json.dumps(kw_list, ensure_ascii=False)

        intent = Intent(
            business_id=business_id,
            name=name,
            keywords=kw_json,
            response=response_text,
            priority=priority,
            button_url=row.get("button_url", ""),
            button_open_new_tab=True,
        )
        db.add(intent)
        db.flush()  # get intent.id

        translation = IntentTranslation(
            intent_id=intent.id,
            language_code=default_lang,
            keywords=kw_json,
            response=response_text,
            button_label=row.get("button_label", ""),
            auto_translated=False,
            needs_review=False,
        )
        db.add(translation)
        existing_names.add(name)
        created += 1

    db.commit()
    return ImportResult(created=created, skipped=skipped, errors=errors)
