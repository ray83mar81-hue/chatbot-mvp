def test_get_business(auth_client):
    res = auth_client.get("/business/1")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["name"] == "Test Cafe"
    assert data["phone"] == "+34 600 000 000"


def test_get_business_not_found(auth_client):
    res = auth_client.get("/business/9999")
    assert res.status_code == 404


def test_update_business(auth_client):
    res = auth_client.put("/business/1", json={"name": "Updated Cafe"})
    assert res.status_code == 200
    assert res.json()["name"] == "Updated Cafe"


def test_get_business_requires_auth(client):
    """Unauthenticated requests get 401 — the security boundary."""
    res = client.get("/business/1")
    assert res.status_code == 401
