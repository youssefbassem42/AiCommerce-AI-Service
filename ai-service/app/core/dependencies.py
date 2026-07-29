from fastapi import Depends

from app.api.ai.dependencies import get_ai_service
from app.application.services.chat_service import ChatService


def get_chat_service(
    chat_service: ChatService = Depends(get_ai_service),
) -> ChatService:
    return chat_service
