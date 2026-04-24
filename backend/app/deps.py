"""Shared FastAPI dependencies for authentication and authorization.

Roles:
- client_admin: manages a single business (tied to AdminUser.business_id)
- superadmin: manages the platform. May "impersonate" a business via the
  X-Impersonate-Business-Id header for day-to-day client support.
"""
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.admin_user import AdminUser


_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise _UNAUTHORIZED from e


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AdminUser:
    """Decode the Bearer token and load the current AdminUser from DB.
    Deactivated users (is_active=False) are rejected even with a valid
    token — same 401 as "not authenticated" so the front redirects to login.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _UNAUTHORIZED
    token = authorization.split(" ", 1)[1].strip()
    payload = _decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise _UNAUTHORIZED
    user = db.query(AdminUser).filter(AdminUser.id == int(sub)).first()
    if not user or not bool(user.is_active):
        raise _UNAUTHORIZED
    return user


def require_superadmin(user: AdminUser = Depends(get_current_user)) -> AdminUser:
    """Gatekeeper for platform-level operations."""
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")
    return user


def assert_business_access(
    user: AdminUser, business_id: int, x_impersonate_business_id: int | None = None
) -> int:
    """Check that the user can operate on business_id (read access).

    Returns the effective business_id (useful for endpoints that want to
    respect impersonation — usually a no-op since we already enforce the ID
    in the URL).

    Rules:
    - superadmin: always allowed
    - client_admin: must match their own business_id
    """
    if user.role == "superadmin":
        return business_id
    if user.business_id is None or user.business_id != business_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return business_id


def assert_business_write(user: AdminUser, business_id: int) -> int:
    """Check read access AND that the user is allowed to mutate this tenant's
    data. Viewers are blocked; owners pass through. Superadmin always passes.
    """
    assert_business_access(user, business_id)
    if user.role == "superadmin":
        return business_id
    if (user.tenant_role or "owner") != "owner":
        raise HTTPException(
            status_code=403,
            detail="Read-only role: you cannot modify this business. Ask an owner.",
        )
    return business_id


def require_tenant_owner(user: AdminUser = Depends(get_current_user)) -> AdminUser:
    """For endpoints that manage tenant-level users (invites, removals).
    Superadmin is accepted too (they can manage users on any tenant).
    """
    if user.role == "superadmin":
        return user
    if user.role != "client_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    if (user.tenant_role or "owner") != "owner":
        raise HTTPException(status_code=403, detail="Only the business owner can manage users")
    return user


def resolve_business_id(
    user: AdminUser = Depends(get_current_user),
    x_impersonate_business_id: int | None = Header(default=None, alias="X-Impersonate-Business-Id"),
) -> int:
    """For endpoints that don't carry business_id in the URL.

    Returns the business the user should be operating on:
    - client_admin: their own business_id
    - superadmin: the impersonated business_id (header is required)
    """
    if user.role == "superadmin":
        if not x_impersonate_business_id:
            raise HTTPException(
                status_code=400,
                detail="Superadmin must pass X-Impersonate-Business-Id header to operate on a business",
            )
        return x_impersonate_business_id
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="User has no business assigned")
    return user.business_id
