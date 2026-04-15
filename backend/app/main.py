import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    AdminUser,
    Business,
    BusinessTranslation,
    ContactRequest,
    Intent,
    IntentTranslation,
    Language,
)
from app.routers import auth, business, chat, contact, conversations, intents, languages, metrics

app = FastAPI(title="Chatbot MVP", version="1.0.0")

# CORS — allow widget and admin panel to connect
origins = settings.CORS_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat.router)
app.include_router(business.router)
app.include_router(intents.router)
app.include_router(conversations.router)
app.include_router(metrics.router)
app.include_router(auth.router)
app.include_router(languages.router)
app.include_router(contact.router)


@app.on_event("startup")
def on_startup():
    """Create tables, run lightweight schema migrations, and seed demo data."""
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    _seed_languages()
    _seed_demo_data()
    _backfill_intent_translations()
    _backfill_business_translations()


# Lightweight schema migrations. Each entry is a tuple of
# (table_name, column_name, column_definition_sql). Idempotent — checks if the
# column already exists before adding it. Works with PostgreSQL and SQLite.
SCHEMA_MIGRATIONS = [
    ("businesses", "supported_languages", 'TEXT DEFAULT \'["es"]\''),
    ("businesses", "default_language", "VARCHAR(5) DEFAULT 'es'"),
    ("businesses", "welcome_messages", "TEXT DEFAULT '{}'"),
    ("intents", "button_url", "VARCHAR(500) DEFAULT ''"),
    ("intents", "button_open_new_tab", "BOOLEAN DEFAULT 1"),
    # Block 9: contact form
    ("businesses", "contact_form_enabled", "BOOLEAN DEFAULT 0"),
    ("businesses", "contact_notification_email", "VARCHAR(255) DEFAULT ''"),
    ("businesses", "privacy_url", "VARCHAR(500) DEFAULT ''"),
    ("businesses", "whatsapp_phone", "VARCHAR(50) DEFAULT ''"),
    ("businesses", "whatsapp_enabled", "BOOLEAN DEFAULT 0"),
    # BusinessTranslation new columns
    ("business_translations", "welcome", "TEXT DEFAULT ''"),
    ("business_translations", "privacy_url", "VARCHAR(500) DEFAULT ''"),
    ("business_translations", "contact_texts", "TEXT DEFAULT '{}'"),
    # Widget UI texts (title, subtitle, placeholder per language)
    ("businesses", "widget_ui_texts", "TEXT DEFAULT '{}'"),
    # Widget design (color, position, width, height, icon_type, bubble_emoji, bubble_image)
    ("businesses", "widget_design", "TEXT DEFAULT '{}'"),
]


def _migrate_schema():
    """Add missing columns to existing tables. Idempotent."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    with engine.begin() as conn:
        for table, column, definition in SCHEMA_MIGRATIONS:
            if table not in existing_tables:
                continue
            existing_columns = {c["name"] for c in insp.get_columns(table)}
            if column in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


# Default catalog of supported languages. The superadmin will manage this in the future.
DEFAULT_LANGUAGES = [
    {"code": "es", "name": "Spanish",    "native_name": "Español",    "flag_emoji": "🇪🇸", "sort_order": 1},
    {"code": "en", "name": "English",    "native_name": "English",    "flag_emoji": "🇬🇧", "sort_order": 2},
    {"code": "ca", "name": "Catalan",    "native_name": "Català",     "flag_emoji": "🇪🇸", "sort_order": 3},
    {"code": "fr", "name": "French",     "native_name": "Français",   "flag_emoji": "🇫🇷", "sort_order": 4},
    {"code": "de", "name": "German",     "native_name": "Deutsch",    "flag_emoji": "🇩🇪", "sort_order": 5},
    {"code": "it", "name": "Italian",    "native_name": "Italiano",   "flag_emoji": "🇮🇹", "sort_order": 6},
    {"code": "pt", "name": "Portuguese", "native_name": "Português",  "flag_emoji": "🇵🇹", "sort_order": 7},
]


def _seed_languages():
    """Insert the default language catalog. Idempotent — only adds missing rows."""
    db = SessionLocal()
    try:
        existing_codes = {row[0] for row in db.query(Language.code).all()}
        for lang in DEFAULT_LANGUAGES:
            if lang["code"] not in existing_codes:
                db.add(Language(**lang))
        db.commit()
    finally:
        db.close()


def _backfill_intent_translations():
    """
    Ensure every Intent has a translation in its business default language.
    If missing, create one from the legacy keywords/response fields on the
    Intent itself. Idempotent — safe to re-run on every startup.

    This catches two cases:
    1. Intents created before the i18n migration (no translations at all).
    2. Intents whose default-lang row was never created (e.g. they were
       AI-translated to other languages but the source row was somehow lost).
    """
    db = SessionLocal()
    try:
        intents = db.query(Intent).all()
        for intent in intents:
            business = (
                db.query(Business).filter(Business.id == intent.business_id).first()
            )
            default_lang = (business.default_language if business else None) or "es"

            existing = (
                db.query(IntentTranslation)
                .filter(
                    IntentTranslation.intent_id == intent.id,
                    IntentTranslation.language_code == default_lang,
                )
                .first()
            )
            if existing:
                continue

            translation = IntentTranslation(
                intent_id=intent.id,
                language_code=default_lang,
                keywords=intent.keywords or "[]",
                response=intent.response or "",
                button_label="",
                auto_translated=False,
                needs_review=False,
            )
            db.add(translation)
        db.commit()
    finally:
        db.close()


def _seed_demo_data():
    """Insert demo business + intents if the DB is fresh."""
    db = SessionLocal()
    try:
        if db.query(Business).first():
            return  # Already seeded

        biz = Business(
            name="Café Central",
            description="Cafetería artesanal en el centro de la ciudad. "
            "Especialidad en café de origen, pasteles caseros y brunch los fines de semana.",
            schedule=json.dumps(
                {
                    "lunes a viernes": "7:00 - 20:00",
                    "sábados": "8:00 - 21:00",
                    "domingos": "9:00 - 15:00",
                },
                ensure_ascii=False,
            ),
            address="Calle Mayor 42, Centro",
            phone="+34 612 345 678",
            email="hola@cafecentral.com",
            extra_info="WiFi gratis. Aceptamos reservas para grupos de más de 6 personas. "
            "Tenemos opciones veganas y sin gluten. Parking público a 2 minutos.",
        )
        db.add(biz)
        db.commit()
        db.refresh(biz)

        demo_intents = [
            Intent(
                business_id=biz.id,
                name="horarios",
                keywords=json.dumps(
                    ["horario", "hora", "abierto", "abren", "cierran", "horarios"],
                    ensure_ascii=False,
                ),
                response="Nuestros horarios son:\n"
                "• Lunes a viernes: 7:00 - 20:00\n"
                "• Sábados: 8:00 - 21:00\n"
                "• Domingos: 9:00 - 15:00",
                priority=10,
            ),
            Intent(
                business_id=biz.id,
                name="ubicacion",
                keywords=json.dumps(
                    ["donde", "ubicacion", "direccion", "llegar", "mapa", "dirección", "ubicación"],
                    ensure_ascii=False,
                ),
                response="Estamos en Calle Mayor 42, Centro. "
                "Hay parking público a 2 minutos caminando.",
                priority=10,
            ),
            Intent(
                business_id=biz.id,
                name="precios",
                keywords=json.dumps(
                    ["precio", "precios", "cuesta", "vale", "carta", "menu", "menú"],
                    ensure_ascii=False,
                ),
                response="Nuestros precios orientativos:\n"
                "• Café espresso: 1.80€\n"
                "• Café con leche: 2.20€\n"
                "• Tostada con tomate: 3.50€\n"
                "• Brunch completo (fines de semana): 14.90€\n"
                "Consulta la carta completa en el local o pídela por email.",
                priority=10,
            ),
            Intent(
                business_id=biz.id,
                name="wifi",
                keywords=json.dumps(
                    ["wifi", "internet", "contraseña", "clave"],
                    ensure_ascii=False,
                ),
                response="Sí, tenemos WiFi gratis. "
                "Pide la contraseña en barra cuando hagas tu pedido.",
                priority=5,
            ),
            Intent(
                business_id=biz.id,
                name="reservas",
                keywords=json.dumps(
                    ["reservar", "reserva", "reservas", "grupo", "grupos", "mesa"],
                    ensure_ascii=False,
                ),
                response="Aceptamos reservas para grupos de más de 6 personas. "
                "Puedes reservar llamando al +34 612 345 678 o enviando un email a hola@cafecentral.com.",
                priority=5,
            ),
        ]
        db.add_all(demo_intents)
        db.commit()
    finally:
        db.close()


def _backfill_business_translations():
    """Ensure every Business has a translation row in its default language."""
    db = SessionLocal()
    try:
        businesses = db.query(Business).all()
        for biz in businesses:
            default_lang = biz.default_language or "es"
            existing = (
                db.query(BusinessTranslation)
                .filter(
                    BusinessTranslation.business_id == biz.id,
                    BusinessTranslation.language_code == default_lang,
                )
                .first()
            )
            if existing:
                continue
            db.add(BusinessTranslation(
                business_id=biz.id,
                language_code=default_lang,
                name=biz.name or "",
                description=biz.description or "",
                address=biz.address or "",
                schedule=biz.schedule or "{}",
                extra_info=biz.extra_info or "",
                auto_translated=False,
                needs_review=False,
            ))
        db.commit()
    finally:
        db.close()


# ── Static files ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # chatbot-mvp/
WIDGET_DIR = PROJECT_ROOT / "widget"
ADMIN_DIR = PROJECT_ROOT / "admin"

FLAGS_DIR = PROJECT_ROOT / "flags"

if WIDGET_DIR.exists():
    app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR)), name="widget")
if FLAGS_DIR.exists():
    app.mount("/flags", StaticFiles(directory=str(FLAGS_DIR)), name="flags")
if ADMIN_DIR.exists():
    app.mount("/admin", StaticFiles(directory=str(ADMIN_DIR), html=True), name="admin")


@app.get("/")
def root():
    return {
        "app": "Chatbot MVP",
        "version": "1.0.0",
        "endpoints": {
            "admin": "/admin",
            "widget_demo": "/widget/demo.html",
            "api_docs": "/docs",
            "health": "/health",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}
