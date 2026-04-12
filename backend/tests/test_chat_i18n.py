"""Integration tests for the multilingual chat flow.

The conftest seeds two intents:
- 'horarios' with only ES translation
- 'wifi' with both ES and EN translations
"""


def test_chat_es_matches_intent(client):
    res = client.post(
        "/chat/message",
        json={
            "message": "¿cuál es el horario?",
            "session_id": "i18n-es-1",
            "business_id": 1,
            "language": "es",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "intent"
    assert data["language"] == "es"
    assert "9:00" in data["response"]


def test_chat_en_matches_intent_with_translation(client):
    """The wifi intent has an EN translation, so it should match in English."""
    res = client.post(
        "/chat/message",
        json={
            "message": "do you have wifi here?",
            "session_id": "i18n-en-1",
            "business_id": 1,
            "language": "en",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "intent"
    assert data["language"] == "en"
    assert "free WiFi" in data["response"]


def test_chat_en_falls_back_to_ai_when_no_translation(client):
    """The horarios intent has NO English translation, so it should NOT match
    in English — falling through to the AI fallback."""
    res = client.post(
        "/chat/message",
        json={
            "message": "what are your opening hours?",
            "session_id": "i18n-en-2",
            "business_id": 1,
            "language": "en",
        },
    )
    assert res.status_code == 200
    data = res.json()
    # Should NOT be matched as intent (no EN translation for horarios)
    assert data["source"] != "intent" or data["intent_name"] != "horarios"
    assert data["language"] == "en"


def test_chat_language_defaults_to_business_default(client):
    """If no language is sent, the chat falls back to business.default_language."""
    res = client.post(
        "/chat/message",
        json={
            "message": "horario?",
            "session_id": "i18n-default-1",
            "business_id": 1,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "es"  # business default


def test_chat_response_includes_language_field(client):
    res = client.post(
        "/chat/message",
        json={
            "message": "wifi",
            "session_id": "i18n-lang-field",
            "business_id": 1,
            "language": "es",
        },
    )
    assert "language" in res.json()


def test_chat_with_intent_button(client):
    """An intent with a button URL should return the button in the response."""
    import json as _json

    # Create an intent with a button
    iid = client.post(
        "/intents/",
        json={
            "business_id": 1,
            "name": "reservas_btn",
            "keywords": _json.dumps(["reserva"]),
            "response": "Para reservar pulsa el botón",
            "priority": 100,
            "button_url": "https://example.com/{lang}/book",
            "button_open_new_tab": True,
        },
    ).json()["id"]

    # Add a button label to the ES translation
    client.put(
        f"/intents/{iid}/translations/es",
        json={
            "keywords": _json.dumps(["reserva"]),
            "response": "Para reservar pulsa el botón",
            "button_label": "Reservar",
        },
    )

    res = client.post(
        "/chat/message",
        json={
            "message": "quiero hacer una reserva",
            "session_id": "i18n-btn-1",
            "business_id": 1,
            "language": "es",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "intent"
    assert data["button"] is not None
    assert data["button"]["label"] == "Reservar"
    # The {lang} placeholder should be replaced with "es"
    assert data["button"]["url"] == "https://example.com/es/book"
    assert data["button"]["open_new_tab"] is True

    client.delete(f"/intents/{iid}")


def test_stream_emits_button_event(client):
    """The streaming endpoint should emit a button SSE event when applicable."""
    import json as _json

    iid = client.post(
        "/intents/",
        json={
            "business_id": 1,
            "name": "reservas_stream_btn",
            "keywords": _json.dumps(["reservar"]),
            "response": "Reserva con un click",
            "priority": 100,
            "button_url": "https://example.com/book",
            "button_open_new_tab": True,
        },
    ).json()["id"]
    client.put(
        f"/intents/{iid}/translations/es",
        json={
            "keywords": _json.dumps(["reservar"]),
            "response": "Reserva con un click",
            "button_label": "Reservar",
        },
    )

    res = client.post(
        "/chat/stream",
        json={
            "message": "puedo reservar?",
            "session_id": "i18n-stream-btn",
            "business_id": 1,
            "language": "es",
        },
    )
    assert res.status_code == 200
    body = res.text
    assert '"type": "button"' in body or '"type":"button"' in body
    assert "Reservar" in body

    client.delete(f"/intents/{iid}")
