from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    source = Column(String(20), nullable=True)  # "intent" | "ai" | "fallback"
    intent_matched_id = Column(Integer, ForeignKey("intents.id"), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    # Token usage reported by the AI provider. NULL for intent/fallback messages.
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
    intent_matched = relationship("Intent")
