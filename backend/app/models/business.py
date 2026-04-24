from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    schedule = Column(Text, default="{}")  # JSON string
    address = Column(String(500), default="")
    phone = Column(String(50), default="")
    email = Column(String(255), default="")
    extra_info = Column(Text, default="")  # Free-form context for AI

    # i18n
    supported_languages = Column(Text, default='["es"]')  # JSON list of language codes
    default_language = Column(String(5), default="es")
    welcome_messages = Column(Text, default="{}")  # JSON {lang_code: welcome_text}
    # {lang_code: {title, subtitle, placeholder}} — UI texts of the widget
    widget_ui_texts = Column(Text, default="{}")
    # {color, position, width, height, icon_type, bubble_emoji, bubble_image}
    widget_design = Column(Text, default="{}")

    # Contact form
    contact_form_enabled = Column(Boolean, default=False)
    contact_notification_email = Column(String(255), default="")  # falls back to .email if empty
    privacy_url = Column(String(500), default="")
    whatsapp_phone = Column(String(50), default="")  # E.164 without "+", e.g. "34612345678"
    whatsapp_enabled = Column(Boolean, default=False)

    # Platform-level: superadmin can deactivate a tenant without deleting their data
    is_active = Column(Boolean, default=True, nullable=False)
    # Monthly token cap for this tenant (NULL = unlimited). Superadmin sets this.
    monthly_token_quota = Column(Integer, nullable=True)
    # Timestamp of the last "80% of quota reached" warning email fired for
    # this tenant. Used to avoid spamming once the warning threshold is
    # crossed; compared against the current month start to auto-reset each
    # month (a cleared or <month_start value re-enables the warning).
    quota_warning_sent_at = Column(DateTime, nullable=True)

    # Per-tenant AI configuration (superadmin-managed by default; tenant owners
    # may override from their admin if they bring their own API key).
    # All NULL → fall back to global settings.AI_* env vars (so existing
    # deployments keep working untouched).
    ai_provider = Column(String(20), nullable=True)   # openrouter|openai|anthropic|gemini|grok|custom
    ai_model = Column(String(200), nullable=True)     # model id string
    ai_api_key = Column(String(500), nullable=True)   # plaintext in DB, masked on GET
    ai_base_url = Column(String(500), nullable=True)  # only used when provider=custom
    ai_input_price_per_million = Column(Float, nullable=True)
    ai_output_price_per_million = Column(Float, nullable=True)

    # Public landing page (for clients without their own website).
    # slug is URL-safe identifier, must be unique when set. Served at /negocio/{slug}.
    slug = Column(String(100), nullable=True, unique=True, index=True)
    landing_enabled = Column(Boolean, default=False, nullable=False)
    # Visual template for the landing page: "clean" | "elegant" | "minimal" | "warm"
    landing_theme = Column(String(20), default="clean", nullable=False)
    # Optional external image URL for the landing header (logo). No upload — admin
    # points at an image hosted elsewhere (their own CDN, Imgur, Cloudinary…).
    logo_url = Column(String(500), default="")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    conversations = relationship("Conversation", back_populates="business")
    admin_users = relationship("AdminUser", back_populates="business")
    contact_requests = relationship("ContactRequest", back_populates="business")
    translations = relationship(
        "BusinessTranslation",
        back_populates="business",
        cascade="all, delete-orphan",
    )
