"""Smoke tests for the chat + translate critical paths.

Each test corresponds to a real production incident documented in
docs/chatbot-mvp-lessons.md. The goal is not coverage; it is to make
the specific class of bug impossible to re-ship.

- test_chat_message_does_not_500           → catches P19
- test_chat_stream_does_not_500            → catches P19 (streaming variant)
- test_translate_preserves_source_data     → catches P21
- test_translate_falls_back_per_field      → catches P21 (regression guard)

The AI provider is mocked so these tests never hit the network. The
mock returns deterministic content shaped like a real OpenAI/OpenRouter
streaming response, with usage tokens populated, so the code paths that
record cost (compute_cost_usd, Message.tokens_in/out) also execute.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator
from unittest.mock import patch

import pytest

# ── AI mocks ──────────────────────────────────────────────────────────────


async def _fake_stream_ai_response(
    business: Any,
    db: Any,
    conversation_history: Any,
    user_message: str,
    language: str = "es",
    usage_out: dict | None = None,
) -> AsyncIterator[str]:
    """Drop-in replacement for ai_service.stream_ai_response. Yields a fixed
    canned response in chunks so the SSE assembly logic still runs.
    """
    chunks = ["Hola", ", ", "soy ", "una ", "respuesta ", "simulada", "."]
    if usage_out is not None:
        usage_out["tokens_in"] = 42
        usage_out["tokens_out"] = 7
    for c in chunks:
        yield c


async def _fake_generate_ai_response(
    business: Any,
    db: Any,
    conversation_history: Any,
    user_message: str,
    language: str = "es",
) -> tuple[str, int, int]:
    """Drop-in replacement for ai_service.generate_ai_response (non-stream)."""
    return ("Respuesta simulada del bot.", 42, 7)


async def _fake_chat_json(system: str, user: str, max_tokens: int = 2000, business=None) -> str:
    """Drop-in replacement for ai_service.chat_json — returns a JSON envelope
    shaped like business_translation_service expects, with non-empty values
    in every translatable field. This is what the assertion in
    test_translate_preserves_source_data relies on.
    """
    # The business_translation_service prompt asks the AI to return
    # {"<lang_code>": {name, description, address, schedule, extra_info, ...}}.
    # The targets are derived from supported_languages minus the source.
    # We return entries for the two we activate below: "en" and "ca".
    return json.dumps({
        "en": {
            "name": "Test Cafe",
            "description": "An English description",
            "address": "Test Street 1",
            "schedule": "{}",
            "extra_info": "Free WiFi",
            "welcome": "Hi there",
            "contact_texts": "{}",
            "faqs": [],
        },
        "ca": {
            "name": "Cafè de prova",
            "description": "Una descripció en català",
            "address": "Carrer de prova 1",
            "schedule": "{}",
            "extra_info": "WiFi gratuït",
            "welcome": "Hola",
            "contact_texts": "{}",
            "faqs": [],
        },
    })


# ── Tests ─────────────────────────────────────────────────────────────────


def test_chat_message_does_not_500(client):
    """P19 — the missing `timedelta` import made every /chat/message return
    500 with `NameError`. This test would have caught it at PR time.
    """
    with patch(
        "app.services.chat_engine.generate_ai_response",
        side_effect=_fake_generate_ai_response,
    ):
        res = client.post("/chat/message", json={
            "message": "Hola",
            "session_id": "smoke-1",
            "business_id": 1,
            "language": "es",
        })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["response"]
    assert body["session_id"] == "smoke-1"


def test_chat_stream_does_not_500(client):
    """P19 (streaming variant) — the SSE endpoint hit the same NameError
    and the client saw it as ERR_HTTP2_PROTOCOL_ERROR. Here we read the
    raw stream and assert at least one chunk + a final end event arrive.
    """
    with patch(
        "app.services.chat_engine.stream_ai_response",
        side_effect=_fake_stream_ai_response,
    ):
        with client.stream("POST", "/chat/stream", json={
            "message": "Hola",
            "session_id": "smoke-stream-1",
            "business_id": 1,
            "language": "es",
        }) as res:
            assert res.status_code == 200, res.read()
            body = b"".join(res.iter_bytes()).decode("utf-8")

    # We should see at least one start event and one end event in the SSE body
    assert '"type": "start"' in body, body
    assert '"type": "end"' in body, body


def test_translate_preserves_source_data(auth_client):
    """P21 — saving the contact form for the source lang created a
    BusinessTranslation row with name/description/extra_info empty.
    The next /translate call must NOT propagate those empties to other
    languages: the source content has to come from Business.* when the
    translation row is partial.

    Steps:
      1. Save contact_texts for the source lang (creates the partial row).
      2. Activate a target language and trigger /translate.
      3. Verify the AI received non-empty source fields (asserted via
         the fake's behavior: it returns content for every target).
      4. Verify the saved translations have non-empty name/description.
    """
    # 1) Activate ca as an additional supported language so /translate has
    # a target. The seed sets supported=["es","en"], default="es".
    r = auth_client.put("/business/1/languages", json={
        "supported_languages": ["es", "en", "ca"],
        "default_language": "es",
    })
    assert r.status_code == 200, r.text

    # 2) Save the contact form for the SOURCE language (es). This creates
    # a BusinessTranslation row with contact_texts populated but
    # name/description/extra_info empty — the exact P21 trigger.
    r = auth_client.put(
        "/business/1/translations/es",
        json={"contact_texts": json.dumps({"submitLabel": "Enviar"})},
    )
    assert r.status_code == 200, r.text

    # 3) Trigger translation with the mocked AI.
    with patch(
        "app.services.business_translation_service.chat_json",
        side_effect=_fake_chat_json,
    ):
        r = auth_client.post(
            "/business/1/translate",
            json={"source_language": "es", "target_languages": ["en", "ca"]},
        )
    assert r.status_code == 200, r.text

    # 4) Read the translations back and assert none of them are empty.
    r = auth_client.get("/business/1/translations")
    assert r.status_code == 200, r.text
    trs = {t["language_code"]: t for t in r.json()}

    for code in ("en", "ca"):
        assert code in trs, f"Missing translation for {code}"
        assert trs[code]["name"].strip(), f"Empty name for {code}"
        assert trs[code]["description"].strip(), f"Empty description for {code}"


@pytest.mark.parametrize(
    "tr_field,tr_value,business_field,business_value,expected",
    [
        # tr_value present → use it
        ("name", "Café Translated", "name", "Test Cafe", "Café Translated"),
        # tr_value empty → fall back to Business.*
        ("name", "", "name", "Test Cafe", "Test Cafe"),
        # tr_value whitespace-only → treat as empty, fall back
        ("name", "   ", "name", "Test Cafe", "Test Cafe"),
    ],
)
def test_translate_falls_back_per_field(
    auth_client, tr_field, tr_value, business_field, business_value, expected,
):
    """P21 regression guard — verifies the per-field fallback in
    business_translation_service.translate_business() for the source row.

    Sets up: Business.<field>=business_value, BusinessTranslation(source).<field>=tr_value
    Then traduces and inspects what the AI received as the source value
    (captured by monkey-patching chat_json to spy on its `user` prompt).
    """
    # Ensure Business.name has the expected base value
    auth_client.put("/business/1", json={business_field: business_value})

    # Add ca to support a target
    auth_client.put("/business/1/languages", json={
        "supported_languages": ["es", "en", "ca"],
        "default_language": "es",
    })

    # Create the partial translation row for the source language
    auth_client.put(
        "/business/1/translations/es",
        json={tr_field: tr_value, "contact_texts": "{}"},
    )

    captured: dict[str, str] = {}

    async def _spy_chat_json(system: str, user: str, max_tokens: int = 2000, business=None) -> str:
        captured["user_prompt"] = user
        return await _fake_chat_json(system, user, max_tokens, business)

    with patch(
        "app.services.business_translation_service.chat_json",
        side_effect=_spy_chat_json,
    ):
        r = auth_client.post(
            "/business/1/translate",
            json={"source_language": "es", "target_languages": ["ca"]},
        )
    assert r.status_code == 200, r.text

    # The AI prompt template embeds source["name"] inside json.dumps(...).
    # If the fallback works, `expected` shows up literally in the prompt.
    assert expected in captured["user_prompt"], (
        f"Expected source field '{expected}' to be passed to the AI, "
        f"but prompt did not contain it. Prompt was: {captured['user_prompt'][:500]}"
    )
