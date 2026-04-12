from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ContactRequest(Base):
    """
    A contact form submission from the chat widget. Stores the lead plus
    audit fields needed for GDPR compliance (consent flags, hashed IP,
    user-agent, timestamp).
    """
    __tablename__ = "contact_requests"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id"), nullable=True, index=True
    )

    # Lead data
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    # Consent
    whatsapp_opt_in = Column(Boolean, default=False)
    privacy_accepted = Column(Boolean, nullable=False, default=False)
    privacy_accepted_at = Column(DateTime, nullable=True)

    # Context
    language = Column(String(5), default="es")
    user_agent = Column(String(500), default="")
    ip_hash = Column(String(64), default="")  # SHA256 hex of IP + salt

    # Workflow
    status = Column(String(20), default="new", index=True)  # "new" | "contacted" | "closed"
    notes = Column(Text, default="")  # admin-only

    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    business = relationship("Business", back_populates="contact_requests")
