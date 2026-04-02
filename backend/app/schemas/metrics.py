from pydantic import BaseModel


class DailyCount(BaseModel):
    date: str
    count: int


class TopIntent(BaseModel):
    intent_name: str
    count: int


class MetricsResponse(BaseModel):
    total_conversations: int
    total_messages: int
    messages_by_day: list[DailyCount]
    top_intents: list[TopIntent]
    ai_fallback_rate: float  # Percentage of messages handled by AI vs intents
    avg_response_time_ms: float
