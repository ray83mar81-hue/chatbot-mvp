def test_register_and_login(client):
    # Register
    res = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "secret123",
        "business_id": 1,
    })
    assert res.status_code == 200
    assert "access_token" in res.json()

    # Login
    res = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "secret123",
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password(client):
    # Register first
    client.post("/auth/register", json={
        "email": "user2@example.com",
        "password": "correct",
        "business_id": 1,
    })

    # Wrong password
    res = client.post("/auth/login", json={
        "email": "user2@example.com",
        "password": "wrong",
    })
    assert res.status_code == 401


def test_register_duplicate(client):
    client.post("/auth/register", json={
        "email": "dup@example.com",
        "password": "pass",
        "business_id": 1,
    })
    res = client.post("/auth/register", json={
        "email": "dup@example.com",
        "password": "pass",
        "business_id": 1,
    })
    assert res.status_code == 400
