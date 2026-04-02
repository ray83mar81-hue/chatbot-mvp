from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    session_id = Column(String(100), nullable=False, index=True)
    status = Column(String(20), default="active")  # "active" | "closed"
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)

    business = relationship("Business", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
