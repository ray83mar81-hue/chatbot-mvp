from sqlalchemy import Column, DateTime, Integer, String, Text
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
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    intents = relationship("Intent", back_populates="business")
    conversations = relationship("Conversation", back_populates="business")
    admin_users = relationship("AdminUser", back_populates="business")
