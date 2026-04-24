"""Tenant-level user management. The owner of a business can list, invite
and remove users (owners or viewers) inside their own tenant.
"""
import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import assert_business_access, require_tenant_owner
from app.models.admin_user import AdminUser

router = APIRouter(prefix="/business", tags=["tenant-admins"])


class TenantAdminResponse(BaseModel):
    id: int
    email: str
    tenant_role: str  # "owner" | "viewer"
    is_active: bool = True
    is_self: bool = False

    model_config = {"from_attributes": True}


class InviteTenantAdminRequest(BaseModel):
    email: str
    password: str
    tenant_role: str = "viewer"  # default to safe read-only


class UpdateTenantAdminRequest(BaseModel):
    """Partial update: only fields that are sent are changed. Password, when
    present, replaces the stored hash — no need for the current password
    because an owner is rotating a team member's credential.
    """
    tenant_role: str | None = None   # "owner" | "viewer"
    is_active: bool | None = None
    new_password: str | None = None


@router.get("/{business_id}/admins", response_model=list[TenantAdminResponse])
def list_tenant_admins(
    business_id: int,
    current: AdminUser = Depends(require_tenant_owner),
    db: Session = Depends(get_db),
):
    assert_business_access(current, business_id)
    users = (
        db.query(AdminUser)
        .filter(AdminUser.business_id == business_id, AdminUser.role == "client_admin")
        .order_by(AdminUser.id)
        .all()
    )
    return [
        TenantAdminResponse(
            id=u.id,
            email=u.email,
            tenant_role=u.tenant_role or "owner",
            is_active=bool(u.is_active),
            is_self=(u.id == current.id),
        )
        for u in users
    ]


@router.post("/{business_id}/admins", response_model=TenantAdminResponse, status_code=201)
def invite_tenant_admin(
    business_id: int,
    data: InviteTenantAdminRequest,
    current: AdminUser = Depends(require_tenant_owner),
    db: Session = Depends(get_db),
):
    """Create a new client_admin user inside this tenant."""
    assert_business_access(current, business_id)

    role = (data.tenant_role or "viewer").lower()
    if role not in ("owner", "viewer"):
        raise HTTPException(status_code=422, detail=f"Invalid tenant_role: {role}")
    if not data.email.strip():
        raise HTTPException(status_code=422, detail="Email is required")
    if len(data.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    existing = db.query(AdminUser).filter(AdminUser.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = AdminUser(
        email=data.email.strip(),
        password_hash=bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode(),
        business_id=business_id,
        role="client_admin",
        tenant_role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TenantAdminResponse(
        id=user.id,
        email=user.email,
        tenant_role=user.tenant_role,
        is_active=bool(user.is_active),
        is_self=False,
    )


@router.patch(
    "/{business_id}/admins/{user_id}",
    response_model=TenantAdminResponse,
)
def update_tenant_admin(
    business_id: int,
    user_id: int,
    data: UpdateTenantAdminRequest,
    current: AdminUser = Depends(require_tenant_owner),
    db: Session = Depends(get_db),
):
    """Owner updates a team member: toggle active, change role or rotate
    the password. An owner cannot deactivate nor demote themselves (that
    would lock the tenant out of its own account management).
    """
    assert_business_access(current, business_id)

    user = (
        db.query(AdminUser)
        .filter(
            AdminUser.id == user_id,
            AdminUser.business_id == business_id,
            AdminUser.role == "client_admin",
        )
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found in this tenant")

    payload = data.model_dump(exclude_unset=True)

    if "is_active" in payload:
        if user.id == current.id and payload["is_active"] is False:
            raise HTTPException(
                status_code=400,
                detail="No puedes desactivarte a ti mismo. Pide a otro owner que lo haga.",
            )
        user.is_active = bool(payload["is_active"])

    if "tenant_role" in payload and payload["tenant_role"] is not None:
        new_role = payload["tenant_role"].lower()
        if new_role not in ("owner", "viewer"):
            raise HTTPException(status_code=422, detail=f"Invalid tenant_role: {new_role}")
        if user.id == current.id and new_role != "owner":
            raise HTTPException(
                status_code=400,
                detail="No puedes cambiarte el rol a ti mismo. Pide a otro owner que lo haga.",
            )
        user.tenant_role = new_role

    if "new_password" in payload and payload["new_password"] is not None:
        if len(payload["new_password"]) < 8:
            raise HTTPException(
                status_code=422,
                detail="La contraseña debe tener al menos 8 caracteres",
            )
        user.password_hash = bcrypt.hashpw(
            payload["new_password"].encode(), bcrypt.gensalt()
        ).decode()

    db.commit()
    db.refresh(user)
    return TenantAdminResponse(
        id=user.id,
        email=user.email,
        tenant_role=user.tenant_role,
        is_active=bool(user.is_active),
        is_self=(user.id == current.id),
    )


@router.delete("/{business_id}/admins/{user_id}", status_code=204)
def remove_tenant_admin(
    business_id: int,
    user_id: int,
    current: AdminUser = Depends(require_tenant_owner),
    db: Session = Depends(get_db),
):
    assert_business_access(current, business_id)

    if user_id == current.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot remove yourself. Ask another owner to do it.",
        )

    user = (
        db.query(AdminUser)
        .filter(
            AdminUser.id == user_id,
            AdminUser.business_id == business_id,
            AdminUser.role == "client_admin",
        )
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found in this tenant")

    db.delete(user)
    db.commit()
    return None
