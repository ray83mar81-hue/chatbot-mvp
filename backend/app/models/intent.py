from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Intent(Base):
    __tablename__ = "intents"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(100), nullable=False)  # e.g. "horarios", "precios"
    keywords = Column(Text, default="[]")  # JSON list: ["horario", "abierto", "hora"]
    response = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher = checked first
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    business = relationship("Business", back_populates="intents")
