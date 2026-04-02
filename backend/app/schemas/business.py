from datetime import datetime

from pydantic import BaseModel, EmailStr


class BusinessBase(BaseModel):
    name: str
    description: str = ""
    schedule: str = "{}"  # JSON string
    address: str = ""
    phone: str = ""
    email: str = ""
    extra_info: str = ""


class BusinessCreate(BusinessBase):
    pass


class BusinessUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    schedule: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    extra_info: str | None = None


class BusinessResponse(BusinessBase):
    id: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
