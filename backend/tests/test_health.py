def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_root(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["app"] == "Chatbot MVP"
    assert "endpoints" in data
