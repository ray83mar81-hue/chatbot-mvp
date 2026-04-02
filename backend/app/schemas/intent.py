from datetime import datetime

from pydantic import BaseModel


class IntentBase(BaseModel):
    name: str
    keywords: str = "[]"  # JSON list of strings
    response: str
    is_active: bool = True
    priority: int = 0


class IntentCreate(IntentBase):
    business_id: int


class IntentUpdate(BaseModel):
    name: str | None = None
    keywords: str | None = None
    response: str | None = None
    is_active: bool | None = None
    priority: int | None = None


class IntentResponse(IntentBase):
    id: int
    business_id: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
