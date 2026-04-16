from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Incident(Base):
    """Support log entry: things that went wrong and a superadmin should see.

    Types:
      - "ai_error": chat / translation AI call failed
      - "email_failed": SMTP notification could not be sent
      - "translation_failed": automated translation pipeline errored
      - "rate_limited": (optional, off by default) a business hit a rate limit

    business_id is nullable so platform-wide errors (e.g. misconfigured env)
    can also be logged without a tenant.
    """
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(String(40), nullable=False, index=True)
    message = Column(String(500), nullable=False)
    details = Column(Text, default="")     # longer trace or JSON context
    resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
