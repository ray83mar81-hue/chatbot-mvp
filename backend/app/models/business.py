from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
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

    # Contact form
    contact_form_enabled = Column(Boolean, default=False)
    contact_notification_email = Column(String(255), default="")  # falls back to .email if empty
    privacy_url = Column(String(500), default="")
    whatsapp_phone = Column(String(50), default="")  # E.164 without "+", e.g. "34612345678"
    whatsapp_enabled = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    intents = relationship("Intent", back_populates="business")
    conversations = relationship("Conversation", back_populates="business")
    admin_users = relationship("AdminUser", back_populates="business")
    contact_requests = relationship("ContactRequest", back_populates="business")
    translations = relationship(
        "BusinessTranslation",
        back_populates="business",
        cascade="all, delete-orphan",
    )
