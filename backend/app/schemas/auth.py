from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserCreate(BaseModel):
    email: str
    password: str
    business_id: int
