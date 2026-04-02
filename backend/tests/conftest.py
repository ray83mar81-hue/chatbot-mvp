import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.business import Business
from app.models.intent import Intent

# In-memory SQLite for tests
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


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    # Seed test data
    db = TestSession()
    if not db.query(Business).first():
        biz = Business(
            name="Test Cafe",
            description="A test cafe",
            schedule=json.dumps({"lunes": "9:00 - 18:00"}),
            address="Calle Test 1",
            phone="+34 600 000 000",
            email="test@test.com",
            extra_info="WiFi gratis",
        )
        db.add(biz)
        db.commit()
        db.refresh(biz)

        intents = [
            Intent(
                business_id=biz.id,
                name="horarios",
                keywords=json.dumps(["horario", "hora", "abierto"]),
                response="Lunes: 9:00 - 18:00",
                priority=10,
            ),
            Intent(
                business_id=biz.id,
                name="wifi",
                keywords=json.dumps(["wifi", "internet"]),
                response="Si, tenemos WiFi gratis",
                priority=5,
            ),
        ]
        db.add_all(intents)
        db.commit()
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
