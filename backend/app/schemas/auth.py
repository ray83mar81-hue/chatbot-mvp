from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    business_id: int | None = None


class AdminUserCreate(BaseModel):
    email: str
    password: str
    business_id: int | None = None   # must be None when role == superadmin
    role: str = "client_admin"       # "client_admin" | "superadmin"


class MeResponse(BaseModel):
    id: int
    email: str
    role: str
    business_id: int | None = None
