import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    ActionButton,
    ActionButtonTranslation,
    AdminUser,
    Business,
    BusinessTranslation,
    ContactRequest,
    Language,
)
from app.routers import action_buttons, auth, business, chat, contact, conversations, landing, languages, metrics, superadmin, tenant_admins

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
app.include_router(conversations.router)
app.include_router(metrics.router)
app.include_router(auth.router)
app.include_router(languages.router)
app.include_router(contact.router)
app.include_router(superadmin.router)
app.include_router(tenant_admins.router)
app.include_router(landing.router)
app.include_router(action_buttons.router)


@app.on_event("startup")
def on_startup():
    """Create tables, run lightweight schema migrations, and seed demo data."""
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    _seed_languages()
    _seed_demo_data()
    _backfill_business_translations()
    _promote_superadmin_by_email()


# Lightweight schema migrations. Each entry is a tuple of
# (table_name, column_name, column_definition_sql). Idempotent — checks if the
# column already exists before adding it. Works with PostgreSQL and SQLite.
SCHEMA_MIGRATIONS = [
    ("businesses", "supported_languages", 'TEXT DEFAULT \'["es"]\''),
    ("businesses", "default_language", "VARCHAR(5) DEFAULT 'es'"),
    ("businesses", "welcome_messages", "TEXT DEFAULT '{}'"),
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
    # Language of the conversation (for admin to see + translate to default)
    ("conversations", "language_code", "VARCHAR(5) DEFAULT 'es'"),
    # Role-based access control
    ("admin_users", "role", "VARCHAR(20) DEFAULT 'client_admin' NOT NULL"),
    # Platform-level tenant suspension
    ("businesses", "is_active", "BOOLEAN DEFAULT TRUE NOT NULL"),
    # AI token usage tracking (for cost visibility in the superadmin panel)
    ("messages", "tokens_in", "INTEGER"),
    ("messages", "tokens_out", "INTEGER"),
    # Monthly token quota per tenant (NULL = unlimited)
    ("businesses", "monthly_token_quota", "INTEGER"),
    # Within-tenant role: "owner" | "viewer" (read-only safety)
    ("admin_users", "tenant_role", "VARCHAR(20) DEFAULT 'owner' NOT NULL"),
    # Public landing page for tenants without their own website
    ("businesses", "slug", "VARCHAR(100)"),
    ("businesses", "landing_enabled", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("businesses", "landing_theme", "VARCHAR(20) DEFAULT 'clean' NOT NULL"),
    ("businesses", "logo_url", "VARCHAR(500) DEFAULT ''"),
]


def _migrate_schema():
    """Add missing columns, drop obsolete intent tables/columns. Idempotent."""
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

        # admin_users.business_id nullability (for superadmin rows)
        if "admin_users" in existing_tables:
            cols = {c["name"]: c for c in insp.get_columns("admin_users")}
            biz = cols.get("business_id")
            if biz is not None and not biz.get("nullable", True):
                try:
                    conn.execute(text(
                        "ALTER TABLE admin_users ALTER COLUMN business_id DROP NOT NULL"
                    ))
                except Exception:
                    # SQLite (tests) doesn't support ALTER COLUMN; safe to skip.
                    pass

        # One-shot cleanup of the legacy intent system. After the AI-first
        # refactor, intent responses have already been folded into
        # business_translations.extra_info (commit 1 of Fase 3). These drops
        # remove the dead tables/columns so they don't show up in diagnostics.
        if "messages" in existing_tables:
            msg_cols = {c["name"] for c in insp.get_columns("messages")}
            if "intent_matched_id" in msg_cols:
                try:
                    # Postgres: needs CASCADE to drop the FK constraint.
                    conn.execute(text(
                        "ALTER TABLE messages DROP COLUMN intent_matched_id CASCADE"
                    ))
                except Exception:
                    # SQLite path: DROP COLUMN is supported from 3.35 but
                    # without CASCADE. Try without.
                    try:
                        conn.execute(text("ALTER TABLE messages DROP COLUMN intent_matched_id"))
                    except Exception:
                        pass

        for legacy_table in ("intent_translations", "intents"):
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {legacy_table} CASCADE"))
            except Exception:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {legacy_table}"))
                except Exception:
                    pass


# Default catalog of supported languages.
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


def _seed_demo_data():
    """Insert the demo business + its action buttons on a fresh DB."""
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
            extra_info=(
                "**Servicios:**\n"
                "- WiFi gratis (pide la contraseña en barra)\n"
                "- Terraza climatizada\n"
                "- Reservas para grupos de más de 6 personas (por teléfono o email)\n"
                "- Opciones veganas y sin gluten\n"
                "- Parking público a 2 minutos\n\n"
                "**Precios orientativos:** café espresso 1.80€, café con leche 2.20€, "
                "tostada con tomate 3.50€, brunch completo (fines de semana) 14.90€."
            ),
        )
        db.add(biz)
        db.commit()
        db.refresh(biz)

        # Demo action buttons (chips fijos del widget)
        demo_buttons_spec = [
            ("call",     "+34 612 345 678",                        "Llamar",       30),
            ("map",      "Calle Mayor 42, Centro, Madrid",         "Cómo llegar",  20),
            ("menu",     "https://cafecentral.com/{lang}/carta",   "Ver carta",    10),
            ("whatsapp", "34612345678",                             "WhatsApp",      5),
        ]
        for btype, value, label, priority in demo_buttons_spec:
            btn = ActionButton(
                business_id=biz.id,
                type=btype,
                value=value,
                priority=priority,
            )
            db.add(btn)
            db.flush()
            db.add(ActionButtonTranslation(
                action_button_id=btn.id,
                language_code="es",
                label=label,
            ))
        db.commit()
    finally:
        db.close()


def _promote_superadmin_by_email():
    """If SUPERADMIN_EMAIL is configured, promote that user to superadmin.
    Idempotent — safe to run on every startup.
    """
    if not settings.SUPERADMIN_EMAIL:
        return
    db = SessionLocal()
    try:
        user = (
            db.query(AdminUser)
            .filter(AdminUser.email == settings.SUPERADMIN_EMAIL)
            .first()
        )
        if user and user.role != "superadmin":
            user.role = "superadmin"
            user.business_id = None
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
