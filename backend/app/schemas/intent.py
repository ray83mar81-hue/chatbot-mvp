from datetime import datetime

from pydantic import BaseModel


class IntentBase(BaseModel):
    name: str
    keywords: str = "[]"  # JSON list of strings (legacy / source-language)
    response: str          # Legacy / source-language response
    is_active: bool = True
    priority: int = 0
    button_url: str = ""
    button_open_new_tab: bool = True


class IntentCreate(IntentBase):
    business_id: int


class IntentUpdate(BaseModel):
    name: str | None = None
    keywords: str | None = None
    response: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    button_url: str | None = None
    button_open_new_tab: bool | None = None


class IntentResponse(IntentBase):
    id: int
    business_id: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
