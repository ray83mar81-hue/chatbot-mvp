"""Tests for intent translation CRUD endpoints."""
import json


def _get_intent_id(client, name="horarios"):
    intents = client.get("/intents/?business_id=1").json()
    return next(i["id"] for i in intents if i["name"] == name)


def test_list_translations(client):
    iid = _get_intent_id(client, "horarios")
    res = client.get(f"/intents/{iid}/translations")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["language_code"] == "es"


def test_list_translations_intent_not_found(client):
    res = client.get("/intents/9999/translations")
    assert res.status_code == 404


def test_upsert_creates_new_translation(client):
    iid = _get_intent_id(client, "horarios")
    res = client.put(
        f"/intents/{iid}/translations/en",
        json={
            "keywords": json.dumps(["hours", "schedule"]),
            "response": "We are open Monday: 9-18",
            "button_label": "View hours",
            "needs_review": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language_code"] == "en"
    assert data["response"] == "We are open Monday: 9-18"
    assert data["button_label"] == "View hours"
    assert data["auto_translated"] is False

    # Confirm it's listed now
    list_res = client.get(f"/intents/{iid}/translations")
    codes = [t["language_code"] for t in list_res.json()]
    assert "en" in codes


def test_upsert_updates_existing_translation(client):
    iid = _get_intent_id(client, "horarios")
    # First create
    client.put(
        f"/intents/{iid}/translations/en",
        json={"response": "First version", "keywords": "[]", "button_label": ""},
    )
    # Then update
    res = client.put(
        f"/intents/{iid}/translations/en",
        json={"response": "Second version"},
    )
    assert res.status_code == 200
    assert res.json()["response"] == "Second version"


def test_upsert_validates_keywords_json(client):
    iid = _get_intent_id(client, "horarios")
    res = client.put(
        f"/intents/{iid}/translations/en",
        json={"keywords": "not-a-json-array", "response": "x"},
    )
    assert res.status_code == 422


def test_upsert_rejects_unknown_language(client):
    iid = _get_intent_id(client, "horarios")
    res = client.put(
        f"/intents/{iid}/translations/xx",
        json={"response": "test"},
    )
    assert res.status_code == 404


def test_create_intent_auto_seeds_default_translation(client):
    res = client.post(
        "/intents/",
        json={
            "business_id": 1,
            "name": "test_seed",
            "keywords": json.dumps(["test"]),
            "response": "Respuesta de prueba",
            "priority": 5,
            "button_url": "",
            "button_open_new_tab": True,
        },
    )
    assert res.status_code == 200
    intent_id = res.json()["id"]

    # Should have an ES translation already
    tres = client.get(f"/intents/{intent_id}/translations")
    translations = tres.json()
    assert len(translations) == 1
    assert translations[0]["language_code"] == "es"
    assert translations[0]["response"] == "Respuesta de prueba"

    client.delete(f"/intents/{intent_id}")


def test_intent_response_includes_button_fields(client):
    """The IntentResponse schema must expose button_url + button_open_new_tab."""
    res = client.post(
        "/intents/",
        json={
            "business_id": 1,
            "name": "with_button",
            "keywords": "[]",
            "response": "Reserva ahora",
            "priority": 5,
            "button_url": "https://example.com/{lang}/book",
            "button_open_new_tab": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["button_url"] == "https://example.com/{lang}/book"
    assert data["button_open_new_tab"] is False
    client.delete(f"/intents/{data['id']}")
