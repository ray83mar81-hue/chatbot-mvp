import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.business import Business
from app.models.contact_request import ContactRequest
from app.models.language import Language

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
def db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()
