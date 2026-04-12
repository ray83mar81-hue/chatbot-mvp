from datetime import datetime

from pydantic import BaseModel


class IntentTranslationBase(BaseModel):
    language_code: str
    keywords: str = "[]"  # JSON list of strings
    response: str
    button_label: str = ""


class IntentTranslationCreate(IntentTranslationBase):
    pass


class IntentTranslationUpdate(BaseModel):
    keywords: str | None = None
    response: str | None = None
    button_label: str | None = None
    needs_review: bool | None = None  # admin can mark as reviewed/approved


class IntentTranslationResponse(IntentTranslationBase):
    id: int
    intent_id: int
    auto_translated: bool
    needs_review: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class TranslateIntentRequest(BaseModel):
    """POST /intents/{id}/translate body."""
    target_languages: list[str] | None = None  # None = all supported by business minus source
    source_language: str | None = None         # None = business default
    overwrite_reviewed: bool = False


class TranslateIntentResponse(BaseModel):
    intent_id: int
    source_language: str
    translations: list[IntentTranslationResponse]
