from pydantic import BaseModel


class DailyCount(BaseModel):
    date: str
    count: int


class MetricsResponse(BaseModel):
    total_conversations: int
    total_messages: int
    messages_by_day: list[DailyCount]
    avg_response_time_ms: float
