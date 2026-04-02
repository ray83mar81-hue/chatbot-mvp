from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_engine import process_message, process_message_stream

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Receive a user message and return the chatbot response."""
    return await process_message(request, db)


@router.post("/stream")
async def stream_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Receive a user message and stream the response via SSE."""
    return StreamingResponse(
        process_message_stream(request, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
