"""Tests for the language catalog and per-business language settings."""


def test_list_languages(client):
    res = client.get("/languages/")
    assert res.status_code == 200
    langs = res.json()
    codes = [l["code"] for l in langs]
    assert "es" in codes
    assert "en" in codes
    assert all("native_name" in l for l in langs)
    assert all("flag_emoji" in l for l in langs)


def test_get_business_languages(client):
    res = client.get("/business/1/languages")
    assert res.status_code == 200
    data = res.json()
    assert data["business_id"] == 1
    assert data["default_language"] == "es"
    codes = [l["code"] for l in data["supported"]]
    assert codes == ["es", "en"]  # order should match supported_languages
    assert data["welcome_messages"]["es"] == "Hola test"
    assert data["welcome_messages"]["en"] == "Hi test"


def test_update_business_languages(client):
    res = client.put(
        "/business/1/languages",
        json={
            "supported_languages": ["es", "en", "ca"],
            "default_language": "es",
            "welcome_messages": {"es": "Hola", "en": "Hi", "ca": "Hola"},
        },
    )
    assert res.status_code == 200
    assert len(res.json()["supported"]) == 3

    # Verify persisted
    res = client.get("/business/1/languages")
    assert [l["code"] for l in res.json()["supported"]] == ["es", "en", "ca"]


def test_update_business_languages_rejects_unknown_code(client):
    res = client.put(
        "/business/1/languages",
        json={"supported_languages": ["es", "xx"]},
    )
    assert res.status_code == 422
    assert "xx" in res.json()["detail"]


def test_update_business_languages_default_must_be_in_supported(client):
    # Default 'fr' is not in supported_languages list
    res = client.put(
        "/business/1/languages",
        json={"supported_languages": ["es", "en"], "default_language": "fr"},
    )
    assert res.status_code == 422
    assert "default_language" in res.json()["detail"]


def test_update_business_languages_rejects_empty_list(client):
    res = client.put(
        "/business/1/languages",
        json={"supported_languages": []},
    )
    assert res.status_code == 422


def test_get_languages_business_not_found(client):
    res = client.get("/business/9999/languages")
    assert res.status_code == 404
