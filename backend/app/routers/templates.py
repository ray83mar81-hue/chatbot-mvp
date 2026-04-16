"""Sector templates — pre-configured intents + business text suggestions.

GET /templates → list available templates (metadata only).
GET /templates/{template_id} → full payload with all intents.
POST /business/{business_id}/apply-template → apply the template to a tenant.

Applying never destructs: existing intents (by name) are skipped;
description / extra_info / welcome are filled only if currently empty.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import assert_business_write, get_current_user
from app.models.admin_user import AdminUser
from app.models.business import Business
from app.models.business_translation import BusinessTranslation
from app.models.intent import Intent
from app.models.intent_translation import IntentTranslation
from app.templates import SECTOR_TEMPLATES

router = APIRouter(tags=["templates"])


# ── Schemas ──────────────────────────────────────────────────────────


class TemplateSummary(BaseModel):
    id: str
    name: str
    icon: str
    description: str
    intent_count: int


class TemplateIntent(BaseModel):
    name: str
    keywords: list[str]
    response: str
    priority: int = 10


class TemplateDetail(BaseModel):
    id: str
    name: str
    icon: str
    description: str
    business_description: str
    extra_info: str
    welcome: str
    intents: list[TemplateIntent]


class ApplyTemplateRequest(BaseModel):
    template_id: str
    overwrite_business_text: bool = False   # if true, replaces description/extra_info even if filled


class ApplyResult(BaseModel):
    template_id: str
    intents_created: int
    intents_skipped: list[str]   # names that already existed
    business_description_updated: bool
    extra_info_updated: bool
    welcome_updated: bool


# ── Helpers ──────────────────────────────────────────────────────────


def _template_by_id(template_id: str):
    return next((t for t in SECTOR_TEMPLATES if t["id"] == template_id), None)


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/templates", response_model=list[TemplateSummary])
def list_templates(_: AdminUser = Depends(get_current_user)):
    return [
        TemplateSummary(
            id=t["id"],
            name=t["name"],
            icon=t["icon"],
            description=t["description"],
            intent_count=len(t["intents"]),
        )
        for t in SECTOR_TEMPLATES
    ]


@router.get("/templates/{template_id}", response_model=TemplateDetail)
def get_template(template_id: str, _: AdminUser = Depends(get_current_user)):
    t = _template_by_id(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateDetail(
        id=t["id"], name=t["name"], icon=t["icon"],
        description=t["description"],
        business_description=t["business_description"],
        extra_info=t["extra_info"],
        welcome=t["welcome"],
        intents=[
            TemplateIntent(
                name=i["name"], keywords=i["keywords"],
                response=i["response"], priority=i.get("priority", 10),
            )
            for i in t["intents"]
        ],
    )


@router.post("/business/{business_id}/apply-template", response_model=ApplyResult)
def apply_template(
    business_id: int,
    data: ApplyTemplateRequest,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_write(current, business_id)
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    tmpl = _template_by_id(data.template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Template '{data.template_id}' not found")

    default_lang = business.default_language or "es"

    # Existing intents by name (so we can skip duplicates)
    existing_names = {
        n for (n,) in
        db.query(Intent.name).filter(Intent.business_id == business_id).all()
    }

    intents_created = 0
    intents_skipped: list[str] = []

    for intent_data in tmpl["intents"]:
        name = intent_data["name"]
        if name in existing_names:
            intents_skipped.append(name)
            continue
        kw_json = json.dumps(intent_data["keywords"], ensure_ascii=False)
        intent = Intent(
            business_id=business_id,
            name=name,
            keywords=kw_json,
            response=intent_data["response"],
            priority=intent_data.get("priority", 10),
            button_url="",
            button_open_new_tab=True,
        )
        db.add(intent)
        db.flush()  # need intent.id
        # Seed the default-language translation so the matcher can use it
        db.add(IntentTranslation(
            intent_id=intent.id,
            language_code=default_lang,
            keywords=kw_json,
            response=intent_data["response"],
            button_label="",
            auto_translated=False,
            needs_review=False,
        ))
        existing_names.add(name)
        intents_created += 1

    # Business description / extra_info / welcome — fill if empty (or if
    # overwrite_business_text=true)
    description_updated = False
    extra_info_updated = False
    welcome_updated = False

    if data.overwrite_business_text or not (business.description or "").strip():
        business.description = tmpl["business_description"]
        description_updated = True
    if data.overwrite_business_text or not (business.extra_info or "").strip():
        business.extra_info = tmpl["extra_info"]
        extra_info_updated = True

    # Welcome lives in Business.welcome_messages[lang]
    try:
        welcomes = json.loads(business.welcome_messages or "{}")
        if not isinstance(welcomes, dict):
            welcomes = {}
    except Exception:
        welcomes = {}
    if data.overwrite_business_text or not (welcomes.get(default_lang) or "").strip():
        welcomes[default_lang] = tmpl["welcome"]
        business.welcome_messages = json.dumps(welcomes, ensure_ascii=False)
        welcome_updated = True

    # Also seed the default-lang BusinessTranslation row with the sample text
    # so everything stays consistent (description/extra_info are read from
    # there by the matcher + landing).
    bt = (
        db.query(BusinessTranslation)
        .filter_by(business_id=business_id, language_code=default_lang)
        .first()
    )
    if not bt:
        bt = BusinessTranslation(
            business_id=business_id,
            language_code=default_lang,
            name=business.name or "",
            description=business.description or "",
            extra_info=business.extra_info or "",
            welcome=welcomes.get(default_lang, ""),
            auto_translated=False,
            needs_review=False,
        )
        db.add(bt)
    else:
        if description_updated:
            bt.description = business.description
        if extra_info_updated:
            bt.extra_info = business.extra_info
        if welcome_updated:
            bt.welcome = welcomes.get(default_lang, "")

    db.commit()

    return ApplyResult(
        template_id=data.template_id,
        intents_created=intents_created,
        intents_skipped=intents_skipped,
        business_description_updated=description_updated,
        extra_info_updated=extra_info_updated,
        welcome_updated=welcome_updated,
    )
