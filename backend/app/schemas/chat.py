from datetime import datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str
    business_id: int = 1  # Default for MVP single-business
    language: str | None = None  # ISO code; if None, falls back to business default


class ChatButton(BaseModel):
    """Optional CTA button attached to an intent response."""
    label: str
    url: str
    open_new_tab: bool = True


class ChatResponse(BaseModel):
    response: str
    source: str  # "intent" | "ai"
    session_id: str
    language: str
    intent_name: str | None = None
    button: ChatButton | None = None


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    source: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: int
    session_id: str
    status: str
    language_code: str = "es"
    started_at: datetime
    ended_at: datetime | None
    messages: list[MessageResponse] = []

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    id: int
    session_id: str
    status: str
    language_code: str = "es"
    started_at: datetime
    message_count: int
    last_message: str | None

    model_config = {"from_attributes": True}


class TranslateConversationRequest(BaseModel):
    target_language: str | None = None  # defaults to business.default_language


class TranslatedMessage(BaseModel):
    id: int
    role: str
    content: str  # translated
    source: str | None = None
    created_at: datetime


class TranslateConversationResponse(BaseModel):
    conversation_id: int
    source_language: str
    target_language: str
    messages: list[TranslatedMessage]
