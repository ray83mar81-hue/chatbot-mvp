from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.admin_user import AdminUser
from app.schemas.auth import AdminUserCreate, LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter(AdminUser.email == data.email).first()
    if not user or not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _create_token({
        "sub": str(user.id),
        "business_id": user.business_id,
        "role": user.role,
    })
    return LoginResponse(
        access_token=token,
        role=user.role,
        tenant_role=user.tenant_role or "owner",
        business_id=user.business_id,
    )


@router.post("/register", response_model=LoginResponse)
def register(data: AdminUserCreate, db: Session = Depends(get_db)):
    """Bootstrap endpoint: creates the FIRST superadmin when the user table
    is empty. Any subsequent registration must use /auth/admin/register
    (superadmin-only).
    """
    user_count = db.query(AdminUser).count()
    if user_count > 0:
        raise HTTPException(
            status_code=403,
            detail="Registration is restricted. Ask a superadmin to create your account.",
        )

    existing = db.query(AdminUser).filter(AdminUser.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # First user is always promoted to superadmin regardless of payload
    user = AdminUser(
        email=data.email,
        password_hash=bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode(),
        business_id=None,
        role="superadmin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_token({
        "sub": str(user.id),
        "business_id": user.business_id,
        "role": user.role,
    })
    return LoginResponse(
        access_token=token,
        role=user.role,
        tenant_role=user.tenant_role or "owner",
        business_id=user.business_id,
    )


@router.post("/admin/register", response_model=LoginResponse)
def admin_register(
    data: AdminUserCreate,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Superadmin-only endpoint to create new users (client admins or other
    superadmins).
    """
    if current.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")

    role = data.role or "client_admin"
    if role not in ("client_admin", "superadmin"):
        raise HTTPException(status_code=422, detail=f"Invalid role: {role}")

    if role == "client_admin" and not data.business_id:
        raise HTTPException(
            status_code=422,
            detail="client_admin requires business_id",
        )
    business_id = None if role == "superadmin" else data.business_id

    existing = db.query(AdminUser).filter(AdminUser.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = AdminUser(
        email=data.email,
        password_hash=bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode(),
        business_id=business_id,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_token({
        "sub": str(user.id),
        "business_id": user.business_id,
        "role": user.role,
    })
    return LoginResponse(
        access_token=token,
        role=user.role,
        tenant_role=user.tenant_role or "owner",
        business_id=user.business_id,
    )


@router.get("/me", response_model=MeResponse)
def get_me(current: AdminUser = Depends(get_current_user)):
    return MeResponse(
        id=current.id,
        email=current.email,
        role=current.role,
        tenant_role=current.tenant_role or "owner",
        business_id=current.business_id,
    )
