import json


def test_list_intents(client):
    res = client.get("/intents/?business_id=1")
    assert res.status_code == 200
    intents = res.json()
    assert len(intents) >= 2
    names = [i["name"] for i in intents]
    assert "horarios" in names
    assert "wifi" in names


def test_create_intent(client):
    res = client.post("/intents/", json={
        "name": "reservas",
        "keywords": json.dumps(["reserva", "reservar", "mesa"]),
        "response": "Llama al +34 600 000 000 para reservar",
        "priority": 5,
        "business_id": 1,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "reservas"
    assert data["id"] is not None


def test_update_intent(client):
    # Get first intent
    intents = client.get("/intents/?business_id=1").json()
    intent_id = intents[0]["id"]

    res = client.put(f"/intents/{intent_id}", json={"priority": 99})
    assert res.status_code == 200
    assert res.json()["priority"] == 99


def test_delete_intent(client):
    # Create one to delete
    created = client.post("/intents/", json={
        "name": "temp",
        "keywords": "[]",
        "response": "temp",
        "business_id": 1,
    }).json()

    res = client.delete(f"/intents/{created['id']}")
    assert res.status_code == 200

    # Verify gone
    res = client.get(f"/intents/{created['id']}")
    assert res.status_code == 404
