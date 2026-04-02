from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.admin_user import AdminUser
from app.schemas.auth import AdminUserCreate, LoginRequest, LoginResponse

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

    token = _create_token({"sub": str(user.id), "business_id": user.business_id})
    return LoginResponse(access_token=token)


@router.post("/register", response_model=LoginResponse)
def register(data: AdminUserCreate, db: Session = Depends(get_db)):
    existing = db.query(AdminUser).filter(AdminUser.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = AdminUser(
        email=data.email,
        password_hash=bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode(),
        business_id=data.business_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_token({"sub": str(user.id), "business_id": user.business_id})
    return LoginResponse(access_token=token)
