from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    # Nullable for superadmins (they are not tied to a single business)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    # "client_admin" (owner of a single business) or "superadmin" (platform operator)
    role = Column(String(20), nullable=False, default="client_admin")
    created_at = Column(DateTime, server_default=func.now())

    business = relationship("Business", back_populates="admin_users")
