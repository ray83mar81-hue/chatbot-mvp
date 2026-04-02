def test_chat_intent_match(client):
    """Message matching a keyword should return intent response."""
    res = client.post("/chat/message", json={
        "message": "cual es el horario?",
        "session_id": "test-session-1",
        "business_id": 1,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "intent"
    assert "9:00" in data["response"]
    assert data["session_id"] == "test-session-1"


def test_chat_fuzzy_match(client):
    """Typos should still match via fuzzy matching."""
    res = client.post("/chat/message", json={
        "message": "horarioo",
        "session_id": "test-session-2",
        "business_id": 1,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "intent"


def test_chat_wifi_intent(client):
    """WiFi keyword should match wifi intent."""
    res = client.post("/chat/message", json={
        "message": "tienen wifi?",
        "session_id": "test-session-3",
        "business_id": 1,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "intent"
    assert "WiFi" in data["response"]


def test_chat_no_match_falls_to_ai(client):
    """Unknown question should go to AI fallback."""
    res = client.post("/chat/message", json={
        "message": "pueden organizar una fiesta de cumple?",
        "session_id": "test-session-4",
        "business_id": 1,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "ai"


def test_chat_invalid_business(client):
    """Non-existent business should return fallback."""
    res = client.post("/chat/message", json={
        "message": "hola",
        "session_id": "test-session-5",
        "business_id": 9999,
    })
    assert res.status_code == 200
    assert "no se encontr" in res.json()["response"].lower()


def test_chat_creates_conversation(client):
    """Sending a message should create a conversation."""
    client.post("/chat/message", json={
        "message": "hola",
        "session_id": "test-conv-1",
        "business_id": 1,
    })
    res = client.get("/conversations/?business_id=1")
    assert res.status_code == 200
    sessions = [c["session_id"] for c in res.json()]
    assert "test-conv-1" in sessions


def test_stream_endpoint(client):
    """Stream endpoint should return SSE events."""
    res = client.post("/chat/stream", json={
        "message": "horario?",
        "session_id": "test-stream-1",
        "business_id": 1,
    })
    assert res.status_code == 200
    body = res.text
    assert "data:" in body
    assert '"type": "start"' in body or '"type":"start"' in body
    assert '"type": "end"' in body or '"type":"end"' in body
