from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Intent(Base):
    __tablename__ = "intents"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(100), nullable=False)  # internal id, e.g. "horarios", "precios"

    # Source-language content (kept for backwards compatibility and as fallback).
    # The localized versions live in IntentTranslation.
    keywords = Column(Text, default="[]")  # JSON list: ["horario", "abierto", "hora"]
    response = Column(Text, nullable=False)

    # Optional CTA button (URL is shared across languages — supports {lang} placeholder).
    # Per-language label is stored in IntentTranslation.button_label.
    button_url = Column(String(500), default="")
    button_open_new_tab = Column(Boolean, default=True)

    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher = checked first
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    business = relationship("Business", back_populates="intents")
    translations = relationship(
        "IntentTranslation",
        back_populates="intent",
        cascade="all, delete-orphan",
    )
