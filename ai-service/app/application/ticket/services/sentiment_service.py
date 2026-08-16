import logging

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.application.services.chat_service import ChatService
from app.application.ticket.dto.sentiment_dto import SentimentAnalysisRequest, SentimentAnalysisResult
from app.core.ai_settings import ai_settings
from app.infrastructure.prompts.client import get_prompt_client

logger = logging.getLogger(__name__)


class SentimentAnalysisService:
    def __init__(self, chat_service: ChatService):
        self._chat = chat_service

    async def analyze(self, request: SentimentAnalysisRequest) -> SentimentAnalysisResult:
        system_prompt = await get_prompt_client().get("sentiment.system_prompt")
        messages: list[MessageDTO] = [
            MessageDTO(role="system", content=system_prompt),
            MessageDTO(
                role="user",
                content="Conversation messages:\n" + "\n".join(f"- {msg}" for msg in request.messages[-10:]),
            ),
        ]

        ai_request = ChatRequest(
            messages=messages,
            model=ai_settings.DEFAULT_MODEL,
            temperature=0.1,
            max_tokens=512,
            json_mode=True,
        )

        try:
            response = await self._chat.chat(request=ai_request)
            content = response.message.content
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)

            import json

            data = json.loads(content)
            return SentimentAnalysisResult(
                sentiment=data.get("sentiment", "neutral"),
                confidence=float(data.get("confidence", 0.5)),
                category=data.get("category", "general"),
                priority=data.get("priority", "low"),
                summary=data.get("summary", ""),
                suggested_response=data.get("suggested_response", ""),
            )
        except Exception as e:
            logger.warning("Sentiment analysis LLM call failed: %s", e, exc_info=True)
            return SentimentAnalysisResult(
                sentiment="neutral",
                confidence=0.0,
                category="general",
                priority="low",
                summary="Unable to analyze sentiment",
                suggested_response="",
            )
