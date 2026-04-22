from datetime import datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str
    business_id: int = 1
    language: str | None = None  # ISO code; falls back to business default


class ChatResponse(BaseModel):
    response: str
    # "ai" for normal replies, "fallback" when the gate short-circuits or the
    # provider errored and a canned message was served.
    source: str
    session_id: str
    language: str


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
    target_language: str | None = None


class TranslatedMessage(BaseModel):
    id: int
    role: str
    content: str
    source: str | None = None
    created_at: datetime


class TranslateConversationResponse(BaseModel):
    conversation_id: int
    source_language: str
    target_language: str
    messages: list[TranslatedMessage]
