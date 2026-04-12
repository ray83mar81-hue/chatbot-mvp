from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class Language(Base):
    __tablename__ = "languages"

    code = Column(String(5), primary_key=True, index=True)  # ISO 639-1, e.g. "es", "en", "ca"
    name = Column(String(50), nullable=False)               # English name, e.g. "Spanish"
    native_name = Column(String(50), nullable=False)        # Native name, e.g. "Español"
    flag_emoji = Column(String(8), default="")              # e.g. "🇪🇸"
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
