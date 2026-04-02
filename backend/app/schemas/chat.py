from datetime import datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str
    business_id: int = 1  # Default for MVP single-business


class ChatResponse(BaseModel):
    response: str
    source: str  # "intent" | "ai"
    session_id: str
    intent_name: str | None = None


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
    started_at: datetime
    ended_at: datetime | None
    messages: list[MessageResponse] = []

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    id: int
    session_id: str
    status: str
    started_at: datetime
    message_count: int
    last_message: str | None

    model_config = {"from_attributes": True}
