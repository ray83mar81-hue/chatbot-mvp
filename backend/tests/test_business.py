def test_get_business(client):
    res = client.get("/business/1")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Test Cafe"
    assert data["phone"] == "+34 600 000 000"


def test_get_business_not_found(client):
    res = client.get("/business/9999")
    assert res.status_code == 404


def test_update_business(client):
    res = client.put("/business/1", json={"name": "Updated Cafe"})
    assert res.status_code == 200
    assert res.json()["name"] == "Updated Cafe"
