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
    Language,
)
from app.routers import (
    action_buttons,
    ai_config,
    auth,
    business,
    chat,
    contact,
    conversations,
    faqs,
    landing,
    languages,
    metrics,
    superadmin,
    tenant_admins,
)

app = FastAPI(title="Chatbot MVP", version="1.0.0")

# CORS — allow widget and admin panel to connect.
# allow_credentials must stay False: the widget needs to be embeddable on
# arbitrary client domains (CORS_ORIGINS="*"), and the spec forbids
# Access-Control-Allow-Origin: * together with credentials. Auth uses JWT
# in the Authorization header, not cookies, so credentials are not needed.
origins = settings.CORS_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
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
app.include_router(ai_config.router)
app.include_router(faqs.router)


@app.on_event("startup")
def on_startup():
    """Create tables, run lightweight schema migrations, and seed demo data."""
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    _seed_languages()
    _seed_demo_data()
    _backfill_business_translations()
    _migrate_intent_blocks_to_faqs()
    _encrypt_legacy_api_keys()
    _purge_old_conversations()
    _promote_superadmin_by_email()


def _purge_old_conversations():
    """Hard-delete conversations whose last activity is older than the
    tenant's retention window (Business.retention_days, default 365).

    "Last activity" = MAX(messages.created_at), or conversations.started_at
    if the conversation has no messages. Idempotent — re-running just finds
    nothing to delete after the first sweep of the day.

    Runs at every startup; for an MVP redeploying weekly that's plenty,
    and avoids needing a real scheduler. Move to a daily cron when the
    deploy cadence drops below the retention granularity.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    from app.models.conversation import Conversation
    from app.models.message import Message

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        purged_total = 0
        for biz in db.query(Business).all():
            retention = biz.retention_days or 365
            if retention <= 0:
                continue  # never purge if explicitly disabled
            cutoff = now - timedelta(days=retention)

            last_msg_subq = (
                db.query(
                    Message.conversation_id.label("cid"),
                    func.max(Message.created_at).label("last_at"),
                )
                .group_by(Message.conversation_id)
                .subquery()
            )

            old = (
                db.query(Conversation)
                .outerjoin(last_msg_subq, Conversation.id == last_msg_subq.c.cid)
                .filter(
                    Conversation.business_id == biz.id,
                    func.coalesce(last_msg_subq.c.last_at, Conversation.started_at) < cutoff,
                )
                .all()
            )

            for conv in old:
                # Messages first — the FK doesn't have ondelete=CASCADE.
                db.query(Message).filter(Message.conversation_id == conv.id).delete()
                db.delete(conv)
                purged_total += 1
        if purged_total:
            db.commit()
            print(f"[retention] purged {purged_total} stale conversation(s)")
    finally:
        db.close()


def _encrypt_legacy_api_keys():
    """One-shot upgrade: rewrite plaintext businesses.ai_api_key values as
    encrypted tokens once an AI_KEY_ENCRYPTION_SECRET is configured.
    Idempotent — already-encrypted rows (PREFIX-marked) are skipped.
    Silent no-op while the env var is empty (dev/staging without a key).

    Always prints a status line when the secret IS set, even if there are
    zero rows to migrate — that way the operator can confirm the env var
    reached the process by checking Runtime logs after the rebuild.
    """
    if not (settings.AI_KEY_ENCRYPTION_SECRET or "").strip():
        return
    from app.services.key_encryption import PREFIX, encrypt
    db = SessionLocal()
    try:
        rows = db.query(Business).filter(Business.ai_api_key.isnot(None)).all()
        plaintext_count = 0
        already_encrypted = 0
        migrated = 0
        for biz in rows:
            stored = (biz.ai_api_key or "").strip()
            if not stored:
                continue
            if stored.startswith(PREFIX):
                already_encrypted += 1
                continue
            plaintext_count += 1
            biz.ai_api_key = encrypt(stored)
            migrated += 1
        if migrated:
            db.commit()
        print(
            f"[key-encryption] secret active. "
            f"encrypted {migrated} new key(s); "
            f"{already_encrypted} already encrypted from a previous run; "
            f"{len(rows)} tenant API key(s) total."
        )
    finally:
        db.close()


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
    # Per-tenant AI configuration (Fase 5). All NULL → global env fallback.
    ("businesses", "ai_provider", "VARCHAR(20)"),
    ("businesses", "ai_model", "VARCHAR(200)"),
    ("businesses", "ai_api_key", "VARCHAR(500)"),
    ("businesses", "ai_base_url", "VARCHAR(500)"),
    ("businesses", "ai_input_price_per_million", "FLOAT"),
    ("businesses", "ai_output_price_per_million", "FLOAT"),
    # Fase 5.1: 80% quota warning idempotency flag
    ("businesses", "quota_warning_sent_at", "TIMESTAMP"),
    # User-management follow-up: soft-disable flag on admin accounts so an
    # owner can pause access without destroying the user row.
    ("admin_users", "is_active", "BOOLEAN DEFAULT TRUE NOT NULL"),
    # FAQ CRUD: per-language JSON list of {q, a} items, rendered as
    # accordion on the landing and fed structured to the AI prompt.
    ("business_translations", "faqs_json", "TEXT DEFAULT '[]'"),
    # Split WhatsApp visibility: whatsapp_enabled stays as the contact-form
    # consent toggle; the new flag controls the landing-page CTA button only.
    # Default TRUE so existing tenants with whatsapp_enabled+phone keep their
    # landing button. Harmless on fresh tenants until they add a phone.
    ("businesses", "whatsapp_in_landing", "BOOLEAN DEFAULT TRUE NOT NULL"),
    # Conversation retention window in days. After this much inactivity the
    # conversation + its messages are hard-deleted by the startup purge.
    # Default 365 (~Pro plan). Superadmin can override per tenant later.
    ("businesses", "retention_days", "INTEGER DEFAULT 365 NOT NULL"),
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


# Default catalog of supported languages. Must be a subset of
# ALLOWED_LANGUAGE_CODES (enforced below) — adding a language requires
# editing this list AND LANGUAGE_NAMES in ai_service.py so the AI prompt
# and the admin UI stay in sync.
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
    """Insert the default language catalog. Idempotent — only adds missing rows.

    Defensively filters out any code not present in ALLOWED_LANGUAGE_CODES
    so the seed never creates a catalog entry the API would later reject.
    """
    from app.services.ai_service import ALLOWED_LANGUAGE_CODES

    allowed_defaults = [l for l in DEFAULT_LANGUAGES if l["code"] in ALLOWED_LANGUAGE_CODES]
    if len(allowed_defaults) != len(DEFAULT_LANGUAGES):
        dropped = [l["code"] for l in DEFAULT_LANGUAGES if l["code"] not in ALLOWED_LANGUAGE_CODES]
        print(
            f"[seed-languages] skipped codes missing from ALLOWED_LANGUAGE_CODES: {dropped}. "
            f"Add them to LANGUAGE_NAMES in ai_service.py first."
        )

    db = SessionLocal()
    try:
        existing_codes = {row[0] for row in db.query(Language.code).all()}
        for lang in allowed_defaults:
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


# Marker that the legacy Fase-3 intent migration left at the start of the
# folded block in business_translations.extra_info. We use it to find that
# block again now and convert each "## title\nbody" item into a structured
# FAQ entry. After conversion the block is stripped from extra_info so the
# content lives in faqs_json only.
INTENT_MIGRATION_MARKER = "<!-- intents-migrated -->"


def _parse_intent_block_to_faqs(block_text: str) -> list[dict]:
    """Split a markdown chunk shaped like

        ## title
        body
        body cont.

        ## next
        ...

    into a list of {"q": ..., "a": ...} dicts. Slug titles like
    "encargos_grupo" get prettified to "Encargos grupo" so the admin sees
    something legible immediately (they can edit afterwards).
    """
    import re
    if not block_text:
        return []
    pattern = re.compile(
        r"^##\s+(.+?)$\n?(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    items: list[dict] = []
    for match in pattern.finditer(block_text):
        title = (match.group(1) or "").strip()
        body = (match.group(2) or "").strip()
        if not title:
            continue
        # Slugified intent name → readable title.
        if "_" in title and " " not in title:
            title = title.replace("_", " ").strip()
            if title:
                title = title[0].upper() + title[1:]
        items.append({"q": title, "a": body})
    return items


def _migrate_intent_blocks_to_faqs():
    """Move each tenant's <!-- intents-migrated --> block from extra_info
    into business_translations.faqs_json. Idempotent: skips a translation
    row when faqs_json is already populated.

    After conversion the block is removed from extra_info (admin gets one
    source of truth: the FAQs UI). Untouched rows (no marker) are ignored.
    """
    db = SessionLocal()
    try:
        translations = db.query(BusinessTranslation).all()
        for tr in translations:
            try:
                existing = json.loads(tr.faqs_json or "[]")
            except (json.JSONDecodeError, TypeError):
                existing = []
            if existing:
                continue  # already migrated for this (biz, lang)

            extra = tr.extra_info or ""
            idx = extra.find(INTENT_MIGRATION_MARKER)
            if idx == -1:
                continue

            block = extra[idx:]
            # The migration also wrote a "**Preguntas frecuentes...**" header
            # line right after the marker — skip past the first ## heading.
            faq_start_in_block = block.find("\n## ")
            if faq_start_in_block == -1:
                continue
            faq_text = block[faq_start_in_block:]
            faqs = _parse_intent_block_to_faqs(faq_text)
            if not faqs:
                continue

            tr.faqs_json = json.dumps(faqs, ensure_ascii=False)
            tr.extra_info = extra[:idx].rstrip()
            print(
                f"[faqs-migration] business {tr.business_id} lang {tr.language_code}: "
                f"{len(faqs)} FAQs extracted from extra_info"
            )
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


class RevalidatingStaticFiles(StaticFiles):
    """Force browsers to revalidate every request via ETag (304 when unchanged).

    Without this, host sites cache chat-widget.js for days under the browser's
    heuristic and never pick up new design fields the admin saves. See P15
    in docs/chatbot-mvp-lessons.md.
    """
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


if WIDGET_DIR.exists():
    app.mount("/widget", RevalidatingStaticFiles(directory=str(WIDGET_DIR)), name="widget")
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
