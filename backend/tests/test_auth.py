"""Auth tests.

/auth/register is a BOOTSTRAP endpoint: it only succeeds when the AdminUser
table is empty (creates the first superadmin). After that, /auth/register
returns 403 and new users have to be created via /auth/admin/register by a
logged-in superadmin. These tests cover both paths.
"""


def test_bootstrap_creates_superadmin(client):
    res = client.post("/auth/register", json={
        "email": "first@example.com",
        "password": "secret123",
    })
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["role"] == "superadmin"


def test_bootstrap_blocks_second_register(client):
    # First call seeds the superadmin
    client.post("/auth/register", json={
        "email": "owner@example.com",
        "password": "secret123",
    })
    # Subsequent /auth/register calls must be locked
    res = client.post("/auth/register", json={
        "email": "second@example.com",
        "password": "secret456",
    })
    assert res.status_code == 403


def test_login_after_bootstrap(client):
    client.post("/auth/register", json={
        "email": "owner@example.com",
        "password": "correct",
    })
    res = client.post("/auth/login", json={
        "email": "owner@example.com",
        "password": "correct",
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "email": "owner@example.com",
        "password": "correct",
    })
    res = client.post("/auth/login", json={
        "email": "owner@example.com",
        "password": "wrong",
    })
    assert res.status_code == 401
