"""AI translation service for Business fields (name, description, address, extra_info)."""
import json

from sqlalchemy.orm import Session

from app.config import settings
from app.models.business import Business
from app.models.business_translation import BusinessTranslation
from app.models.language import Language
from app.services.ai_service import _get_client
from app.services.translation_service import TranslationError, _extract_json


def _build_prompt(
    source_language_name: str,
    source: dict,
    targets: list[dict],
) -> str:
    targets_block = "\n".join(
        f'- "{t["code"]}" ({t["name"]} / {t["native_name"]})' for t in targets
    )
    return f"""You are a professional translator for a business website. Translate the source content from {source_language_name} into each target language.

Target languages:
{targets_block}

Source content:
- name (business name): {json.dumps(source["name"], ensure_ascii=False)}
- description: {json.dumps(source["description"], ensure_ascii=False)}
- address: {json.dumps(source["address"], ensure_ascii=False)}
- schedule (opening hours, JSON string with day names as keys): {json.dumps(source["schedule"], ensure_ascii=False)}
- extra_info (additional info for customers): {json.dumps(source["extra_info"], ensure_ascii=False)}
- welcome (greeting message shown when chat opens): {json.dumps(source["welcome"], ensure_ascii=False)}

Rules:
- Translate naturally and idiomatically.
- Keep proper nouns (brand names, street names) unchanged unless they have an official localized form.
- Preserve phone numbers, emails, URLs unchanged.
- The business name should generally stay the same unless it has an established localized variant.
- For schedule: translate the day names (e.g. "lunes" → "Monday") but keep the hours unchanged. Keep it as a valid JSON string.
- Output ONLY a JSON object, no markdown fences.

Output schema:
{{
  "<lang_code>": {{
    "name": "...",
    "description": "...",
    "address": "...",
    "schedule": "...",
    "extra_info": "...",
    "welcome": "..."
  }}
}}
"""


async def translate_business(
    business: Business,
    source_language_code: str,
    target_language_codes: list[str],
    db: Session,
    overwrite_reviewed: bool = False,
) -> list[BusinessTranslation]:
    if not target_language_codes:
        return []

    languages = (
        db.query(Language)
        .filter(Language.code.in_(target_language_codes + [source_language_code]))
        .all()
    )
    by_code = {lang.code: lang for lang in languages}

    if source_language_code not in by_code:
        raise TranslationError(f"Unknown source language: {source_language_code}")

    targets = []
    for code in target_language_codes:
        if code == source_language_code:
            continue
        lang = by_code.get(code)
        if not lang:
            raise TranslationError(f"Unknown target language: {code}")
        targets.append({"code": lang.code, "name": lang.name, "native_name": lang.native_name})

    if not targets:
        return []

    # Get source content from the source-lang translation row, or legacy fields
    src_row = (
        db.query(BusinessTranslation)
        .filter_by(business_id=business.id, language_code=source_language_code)
        .first()
    )
    if src_row:
        source = {"name": src_row.name, "description": src_row.description,
                  "address": src_row.address, "schedule": src_row.schedule or "{}",
                  "extra_info": src_row.extra_info, "welcome": src_row.welcome or ""}
    else:
        # Fallback: get welcome from welcome_messages JSON on the business
        import json as _json
        try:
            welcomes = _json.loads(business.welcome_messages or "{}")
        except Exception:
            welcomes = {}
        source = {"name": business.name, "description": business.description,
                  "address": business.address, "schedule": business.schedule or "{}",
                  "extra_info": business.extra_info,
                  "welcome": welcomes.get(source_language_code, "")}

    prompt = _build_prompt(
        source_language_name=by_code[source_language_code].name,
        source=source,
        targets=targets,
    )

    client = _get_client()
    try:
        response = await client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=2000,
            system="You are a professional translator. Reply with valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text
    except Exception as e:
        raise TranslationError(f"AI request failed: {type(e).__name__}: {e}") from e

    parsed = _extract_json(raw_text)

    saved: list[BusinessTranslation] = []
    for target in targets:
        code = target["code"]
        entry = parsed.get(code)
        if not isinstance(entry, dict):
            continue

        existing = (
            db.query(BusinessTranslation)
            .filter_by(business_id=business.id, language_code=code)
            .first()
        )

        new_data = {
            "name": str(entry.get("name") or "").strip(),
            "description": str(entry.get("description") or "").strip(),
            "address": str(entry.get("address") or "").strip(),
            "schedule": str(entry.get("schedule") or "{}").strip(),
            "extra_info": str(entry.get("extra_info") or "").strip(),
            "welcome": str(entry.get("welcome") or "").strip(),
        }

        if existing:
            is_human_approved = not existing.auto_translated and not existing.needs_review
            if is_human_approved and not overwrite_reviewed:
                continue
            for k, v in new_data.items():
                setattr(existing, k, v)
            existing.auto_translated = True
            existing.needs_review = True
            saved.append(existing)
        else:
            row = BusinessTranslation(
                business_id=business.id,
                language_code=code,
                auto_translated=True,
                needs_review=True,
                **new_data,
            )
            db.add(row)
            saved.append(row)

    db.commit()
    for t in saved:
        db.refresh(t)
    return saved
