"""Unit tests for the AI translation service.

The Anthropic client is mocked so these tests run instantly and don't burn
tokens. We verify the parser is robust, target/source language handling is
correct, and the upsert/no-clobber logic behaves as designed.
"""
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.models.intent import Intent
from app.models.intent_translation import IntentTranslation
from app.services.translation_service import (
    TranslationError,
    _extract_json,
    translate_intent,
)


# ── _extract_json: parser robustness ─────────────────────────────────


def test_extract_json_clean():
    r = _extract_json('{"en": {"keywords": ["x"], "response": "y", "button_label": ""}}')
    assert r["en"]["response"] == "y"


def test_extract_json_markdown_fence():
    raw = '```json\n{"en": {"response": "hi"}}\n```'
    assert _extract_json(raw)["en"]["response"] == "hi"


def test_extract_json_text_around():
    raw = 'Sure! {"en": {"response": "hi"}} Done.'
    assert _extract_json(raw)["en"]["response"] == "hi"


def test_extract_json_invalid_raises():
    with pytest.raises(TranslationError):
        _extract_json("not json at all")


# ── translate_intent (mocked AI) ──────────────────────────────────────


def _make_mock_response(payload: dict) -> AsyncMock:
    """Build a fake Anthropic response with the given JSON payload."""
    mock_msg = type("MockMsg", (), {})()
    mock_msg.content = [type("MockContent", (), {"text": json.dumps(payload)})()]
    mock_create = AsyncMock(return_value=mock_msg)
    return mock_create


def test_translate_intent_creates_translations(db):
    from app.models.business import Business
    biz = db.query(Business).first()
    intent = db.query(Intent).filter(Intent.business_id == biz.id, Intent.name == "horarios").first()
    assert intent is not None

    fake_payload = {
        "en": {
            "keywords": ["hours", "schedule"],
            "response": "Open Mon: 9-18",
            "button_label": "",
        },
    }

    with patch("app.services.translation_service._get_client") as mock_client:
        mock_client.return_value.messages.create = _make_mock_response(fake_payload)
        results = asyncio.run(
            translate_intent(
                intent=intent,
                source_language_code="es",
                target_language_codes=["en"],
                db=db,
            )
        )

    assert len(results) == 1
    assert results[0].language_code == "en"
    assert results[0].response == "Open Mon: 9-18"
    assert results[0].auto_translated is True
    assert results[0].needs_review is True


def test_translate_intent_skips_source_language(db):
    """Asking for source==target should not create or call AI."""
    from app.models.business import Business
    biz = db.query(Business).first()
    intent = db.query(Intent).filter(Intent.business_id == biz.id, Intent.name == "horarios").first()

    with patch("app.services.translation_service._get_client") as mock_client:
        mock_create = AsyncMock()
        mock_client.return_value.messages.create = mock_create

        results = asyncio.run(
            translate_intent(
                intent=intent,
                source_language_code="es",
                target_language_codes=["es"],  # same as source
                db=db,
            )
        )

    assert results == []
    # AI was never called because the only target equals the source
    mock_create.assert_not_called()


def test_translate_intent_does_not_overwrite_reviewed(db):
    """A human-reviewed translation should NOT be replaced by an auto-translation."""
    from app.models.business import Business
    biz = db.query(Business).first()
    intent = db.query(Intent).filter(Intent.business_id == biz.id, Intent.name == "wifi").first()

    # The wifi intent already has a reviewed EN translation in the conftest seed
    existing = (
        db.query(IntentTranslation)
        .filter_by(intent_id=intent.id, language_code="en")
        .first()
    )
    assert existing is not None
    assert existing.auto_translated is False
    assert existing.needs_review is False
    original_response = existing.response

    fake_payload = {
        "en": {
            "keywords": ["wifi", "internet"],
            "response": "AI-GENERATED REPLACEMENT",
            "button_label": "",
        },
    }

    with patch("app.services.translation_service._get_client") as mock_client:
        mock_client.return_value.messages.create = _make_mock_response(fake_payload)
        results = asyncio.run(
            translate_intent(
                intent=intent,
                source_language_code="es",
                target_language_codes=["en"],
                db=db,
                overwrite_reviewed=False,
            )
        )

    # Reload from DB
    db.refresh(existing)
    assert existing.response == original_response  # NOT clobbered
    assert results == []  # nothing was saved


def test_translate_intent_overwrites_when_forced(db):
    """overwrite_reviewed=True should replace even reviewed translations."""
    from app.models.business import Business
    biz = db.query(Business).first()
    intent = db.query(Intent).filter(Intent.business_id == biz.id, Intent.name == "wifi").first()

    fake_payload = {
        "en": {
            "keywords": ["wifi"],
            "response": "FORCED REPLACEMENT",
            "button_label": "",
        },
    }

    with patch("app.services.translation_service._get_client") as mock_client:
        mock_client.return_value.messages.create = _make_mock_response(fake_payload)
        asyncio.run(
            translate_intent(
                intent=intent,
                source_language_code="es",
                target_language_codes=["en"],
                db=db,
                overwrite_reviewed=True,
            )
        )

    existing = (
        db.query(IntentTranslation)
        .filter_by(intent_id=intent.id, language_code="en")
        .first()
    )
    assert existing.response == "FORCED REPLACEMENT"
    assert existing.auto_translated is True
    assert existing.needs_review is True


def test_translate_intent_unknown_target_raises(db):
    from app.models.business import Business
    biz = db.query(Business).first()
    intent = db.query(Intent).filter(Intent.business_id == biz.id).first()

    with pytest.raises(TranslationError):
        asyncio.run(
            translate_intent(
                intent=intent,
                source_language_code="es",
                target_language_codes=["xx"],
                db=db,
            )
        )


def test_translate_intent_endpoint_uses_business_supported_languages(client):
    """POST /intents/{id}/translate with no target_languages should default to
    business.supported_languages minus the source."""
    iid = client.get("/intents/?business_id=1").json()[0]["id"]

    fake_payload = {
        "en": {
            "keywords": ["test"],
            "response": "test response",
            "button_label": "",
        }
    }

    with patch("app.services.translation_service._get_client") as mock_client:
        mock_client.return_value.messages.create = _make_mock_response(fake_payload)
        res = client.post(f"/intents/{iid}/translate", json={})

    # The conftest sets supported=['es','en'] and default='es' → target=['en']
    assert res.status_code == 200
    data = res.json()
    assert data["source_language"] == "es"
    assert any(t["language_code"] == "en" for t in data["translations"])


def test_translate_intent_endpoint_intent_not_found(client):
    res = client.post("/intents/9999/translate", json={})
    assert res.status_code == 404
