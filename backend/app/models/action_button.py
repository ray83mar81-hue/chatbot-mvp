from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# Button types. Each maps to a specific widget render + target semantics.
# - "call":     value = phone number. Widget renders tel: link.
# - "whatsapp": value = phone E.164 without +. Widget renders https://wa.me/<value>.
# - "map":      value = address or map URL. Widget renders Google Maps search.
# - "menu":     value = URL (PDF, page). Widget opens it.
# - "url":      value = any URL. Generic link.
# - "custom":   value = any URL; admin picks icon + label.
ACTION_BUTTON_TYPES = ("call", "whatsapp", "map", "menu", "url", "custom")


class ActionButton(Base):
    __tablename__ = "action_buttons"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(
        Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type = Column(String(20), nullable=False, default="url")
    # Destination payload; semantics depend on `type`. Supports {lang} placeholder.
    value = Column(String(1000), default="")
    # Optional emoji override. Empty → widget picks default per type.
    icon = Column(String(10), default="")
    open_new_tab = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # higher = shown first
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    translations = relationship(
        "ActionButtonTranslation",
        back_populates="action_button",
        cascade="all, delete-orphan",
    )
