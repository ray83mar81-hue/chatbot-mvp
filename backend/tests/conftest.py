import os

# IMPORTANT: force test-friendly env vars BEFORE importing app.*. The app
# config evaluates settings at import time (engine = create_engine(...))
# and the default DATABASE_URL is PostgreSQL, which requires psycopg2 and
# a live server. Set sqlite + a dummy JWT secret here so the test process
# never tries to reach a real database. CI relies on this too — the
# workflow does not install psycopg2.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-in-prod")
os.environ.setdefault("AI_KEY_ENCRYPTION_SECRET", "")  # disable Fernet in tests

import json  # noqa: E402

import pytest  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.business import Business  # noqa: E402
from app.models.contact_request import ContactRequest  # noqa: E402,F401
from app.models.language import Language  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


SEED_LANGUAGES = [
    {"code": "es", "name": "Spanish",  "native_name": "Español",   "flag_emoji": "🇪🇸", "sort_order": 1},
    {"code": "en", "name": "English",  "native_name": "English",   "flag_emoji": "🇬🇧", "sort_order": 2},
    {"code": "ca", "name": "Catalan",  "native_name": "Català",    "flag_emoji": "🇪🇸", "sort_order": 3},
    {"code": "fr", "name": "French",   "native_name": "Français",  "flag_emoji": "🇫🇷", "sort_order": 4},
]


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    db = TestSession()
    if not db.query(Language).first():
        for lang in SEED_LANGUAGES:
            db.add(Language(**lang))
        db.commit()

    if not db.query(Business).first():
        biz = Business(
            name="Test Cafe",
            description="A test cafe",
            schedule=json.dumps({"lunes": "9:00 - 18:00"}),
            address="Calle Test 1",
            phone="+34 600 000 000",
            email="test@test.com",
            extra_info="WiFi gratis",
            supported_languages=json.dumps(["es", "en"]),
            default_language="es",
            welcome_messages=json.dumps({"es": "Hola test", "en": "Hi test"}),
            contact_form_enabled=True,
            whatsapp_enabled=True,
            whatsapp_phone="34600000000",
            privacy_url="https://test.com/privacy",
        )
        db.add(biz)
        db.commit()
        db.refresh(biz)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """A TestClient pre-authenticated as a freshly-bootstrapped superadmin.

    Every test runs against a fresh DB (see setup_db autouse) so this fixture
    can safely call /auth/register: the AdminUser table is always empty,
    bootstrap creates the first user as superadmin, and the JWT goes into
    the default headers. Use this for any endpoint guarded by
    require_superadmin or get_current_user.
    """
    res = client.post("/auth/register", json={
        "email": "owner@example.com",
        "password": "secret123",
    })
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()
