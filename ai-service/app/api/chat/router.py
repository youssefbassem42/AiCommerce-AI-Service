from fastapi import APIRouter, Depends

from app.api.ai.dependencies import get_ai_service
from app.api.chat.schemas import ChatRequest, ChatResponse
from app.application.dto.ai_dto import ChatRequest as AIChatRequest, MessageDTO
from app.application.services.chat_service import ChatService
from app.core.ai_settings import ai_settings

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_ai_service),
) -> ChatResponse:
    response = await chat_service.chat(
        AIChatRequest(
            messages=[MessageDTO(role="user", content=request.message)],
            model=ai_settings.DEFAULT_MODEL,
        )
    )
    content = response.message.content
    return ChatResponse(response=content if isinstance(content, str) else str(content))
