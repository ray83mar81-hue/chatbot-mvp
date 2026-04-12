from datetime import datetime

from pydantic import BaseModel


class BusinessTranslationResponse(BaseModel):
    id: int
    business_id: int
    language_code: str
    name: str
    description: str
    address: str
    schedule: str
    extra_info: str
    welcome: str
    privacy_url: str
    contact_texts: str  # JSON
    auto_translated: bool
    needs_review: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class BusinessTranslationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    address: str | None = None
    schedule: str | None = None
    extra_info: str | None = None
    welcome: str | None = None
    privacy_url: str | None = None
    contact_texts: str | None = None  # JSON
    needs_review: bool | None = None


class TranslateBusinessRequest(BaseModel):
    target_languages: list[str] | None = None
    source_language: str | None = None
    overwrite_reviewed: bool = False
