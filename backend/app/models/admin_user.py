from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
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
    # Platform role: "client_admin" (manages a single business) or "superadmin".
    role = Column(String(20), nullable=False, default="client_admin")
    # Within-tenant role: "owner" (full access, can manage users) or "viewer"
    # (read-only — cannot modify config). Irrelevant for superadmins.
    tenant_role = Column(String(20), nullable=False, default="owner")
    # Soft-disable flag. Deactivated users cannot log in and cannot use a
    # previously issued token (get_current_user enforces this). Used by
    # owners/superadmin to pause access without destroying the account.
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, server_default=func.now())

    business = relationship("Business", back_populates="admin_users")
