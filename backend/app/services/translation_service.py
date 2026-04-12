"""
AI translation service for intents.

Given an Intent and a list of target language codes, calls Claude once with a
structured JSON prompt to generate translations of keywords, response, and
button label for all targets at once. Persists the results as IntentTranslation
rows marked auto_translated=True / needs_review=True.

The translation lives separate from the runtime fast-path: at runtime the
intent matcher reads pre-generated rows from intent_translations and never
hits the AI. Only the admin "Generate translations" action consumes tokens.
"""
import json
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.models.intent import Intent
from app.models.intent_translation import IntentTranslation
from app.models.language import Language
from app.services.ai_service import _get_client


class TranslationError(Exception):
    """Raised when the AI response cannot be parsed into translations."""


def _build_prompt(
    source_language_name: str,
    source_keywords: list[str],
    source_response: str,
    source_button_label: str,
    targets: list[dict],
) -> str:
    """Build a structured-JSON translation prompt."""
    targets_block = "\n".join(
        f'- "{t["code"]}" ({t["name"]} / {t["native_name"]})' for t in targets
    )
    return f"""You are a professional translator for a business chatbot. Translate the source content from {source_language_name} into each of the target languages listed below.

Target languages:
{targets_block}

Source content:
- keywords (short words/phrases users might type to trigger this intent): {json.dumps(source_keywords, ensure_ascii=False)}
- response (the bot reply): {json.dumps(source_response, ensure_ascii=False)}
- button_label (optional CTA button text, may be empty): {json.dumps(source_button_label, ensure_ascii=False)}

Rules:
- Translate naturally and idiomatically — do NOT transliterate.
- Keywords should be the words a real native speaker would type for this topic. You may add or remove items if it improves coverage in the target language; aim for 4-8 keywords.
- The response must keep the same tone, length, and meaning as the source. Preserve line breaks, bullet points, prices, phone numbers, emails, addresses and URLs unchanged.
- The button_label should be concise (max ~25 characters). If the source is empty, return an empty string.
- Output ONLY a JSON object, no markdown code fences, no commentary, no explanation.

Output schema (exactly this shape, with one entry per target language code):
{{
  "<lang_code>": {{
    "keywords": ["...", "..."],
    "response": "...",
    "button_label": "..."
  }}
}}
"""


def _extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from the model's reply.
    Handles cases where the model wraps the JSON in ```json ... ``` fences
    or adds a leading/trailing sentence despite the instructions.
    """
    text = text.strip()

    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        # Find the first { and the matching last }
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            text = text[first : last + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise TranslationError(f"AI response was not valid JSON: {e}") from e


def _get_source_payload(
    intent: Intent, source_lang_code: str, db: Session
) -> tuple[list[str], str, str]:
    """
    Resolve the source content to translate FROM. Prefers an existing
    IntentTranslation in the source language, falls back to the legacy
    Intent.keywords/Intent.response fields if none exists.
    """
    source = (
        db.query(IntentTranslation)
        .filter(
            IntentTranslation.intent_id == intent.id,
            IntentTranslation.language_code == source_lang_code,
        )
        .first()
    )
    if source:
        try:
            keywords = json.loads(source.keywords) if source.keywords else []
        except json.JSONDecodeError:
            keywords = []
        return keywords, source.response or "", source.button_label or ""

    # Fallback to legacy intent fields
    try:
        keywords = json.loads(intent.keywords) if intent.keywords else []
    except json.JSONDecodeError:
        keywords = []
    return keywords, intent.response or "", ""


async def translate_intent(
    intent: Intent,
    source_language_code: str,
    target_language_codes: list[str],
    db: Session,
    overwrite_reviewed: bool = False,
) -> list[IntentTranslation]:
    """
    Generate translations for an intent into the requested target languages.

    Calls Claude ONCE for all targets and persists each result as an
    IntentTranslation row marked auto_translated=True, needs_review=True.

    By default, existing translations that have been marked as reviewed
    (needs_review=False, auto_translated=False) are NOT overwritten — pass
    overwrite_reviewed=True to force regeneration.
    """
    if not target_language_codes:
        return []

    # Resolve language metadata for the prompt
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
        targets.append(
            {"code": lang.code, "name": lang.name, "native_name": lang.native_name}
        )

    if not targets:
        return []

    # Get source content
    src_keywords, src_response, src_button = _get_source_payload(
        intent, source_language_code, db
    )

    if not src_response:
        raise TranslationError(
            "Cannot translate: source intent has no response in the source language"
        )

    # Single AI call with structured JSON output
    prompt = _build_prompt(
        source_language_name=by_code[source_language_code].name,
        source_keywords=src_keywords,
        source_response=src_response,
        source_button_label=src_button,
        targets=targets,
    )

    client = _get_client()
    try:
        response = await client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=2000,
            system="You are a professional translator. You always reply with valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text
    except Exception as e:
        raise TranslationError(f"AI request failed: {type(e).__name__}: {e}") from e

    parsed = _extract_json(raw_text)

    # Persist translations
    saved: list[IntentTranslation] = []
    for target in targets:
        code = target["code"]
        entry = parsed.get(code)
        if not isinstance(entry, dict):
            # Skip silently — partial success is better than total failure
            continue

        keywords_list = entry.get("keywords") or []
        if not isinstance(keywords_list, list):
            keywords_list = []
        keywords_json = json.dumps(
            [str(k) for k in keywords_list], ensure_ascii=False
        )
        response_text = str(entry.get("response") or "").strip()
        button_label = str(entry.get("button_label") or "").strip()

        if not response_text:
            continue

        existing = (
            db.query(IntentTranslation)
            .filter(
                IntentTranslation.intent_id == intent.id,
                IntentTranslation.language_code == code,
            )
            .first()
        )

        if existing:
            # Don't clobber a human-reviewed translation unless explicitly told to
            is_human_approved = (
                not existing.auto_translated and not existing.needs_review
            )
            if is_human_approved and not overwrite_reviewed:
                continue
            existing.keywords = keywords_json
            existing.response = response_text
            existing.button_label = button_label
            existing.auto_translated = True
            existing.needs_review = True
            saved.append(existing)
        else:
            new = IntentTranslation(
                intent_id=intent.id,
                language_code=code,
                keywords=keywords_json,
                response=response_text,
                button_label=button_label,
                auto_translated=True,
                needs_review=True,
            )
            db.add(new)
            saved.append(new)

    db.commit()
    for t in saved:
        db.refresh(t)
    return saved
