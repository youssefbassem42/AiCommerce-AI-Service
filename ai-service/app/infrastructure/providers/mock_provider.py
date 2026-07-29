from typing import Any, AsyncGenerator, List, Optional

from app.application.dto.ai_dto import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    HealthDTO,
    MessageDTO,
    StreamingChunkDTO,
    UsageDTO,
)
from app.infrastructure.providers.base import BaseLLMProvider


class MockProvider(BaseLLMProvider):
    async def chat(self, request: ChatRequest, timeout: Optional[float] = None) -> ChatResponse:
        message = request.messages[-1].content if request.messages else ""
        return ChatResponse(
            id="mock-chat",
            model=request.model,
            provider="mock",
            message=MessageDTO(role="assistant", content=f"Mock response: {message}"),
            usage=UsageDTO(),
            latency_ms=0.0,
        )

    async def stream(
        self,
        request: ChatRequest,
        timeout: Optional[float] = None,
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        yield StreamingChunkDTO(
            id="mock-stream",
            model=request.model,
            provider="mock",
            content="Mock response",
            finish_reason="stop",
            usage=UsageDTO(),
        )

    async def embeddings(
        self,
        request: EmbeddingRequest,
        timeout: Optional[float] = None,
    ) -> EmbeddingResponse:
        inputs = request.input if isinstance(request.input, list) else [request.input]
        return EmbeddingResponse(
            model=request.model,
            provider="mock",
            embeddings=[[0.0, 0.0, 0.0] for _ in inputs],
            usage=UsageDTO(),
        )

    async def health_check(self) -> HealthDTO:
        return HealthDTO(status="healthy", provider="mock", latency_ms=0.0, details="Mock provider")

    async def list_models(self) -> List[str]:
        return ["mock-model"]

    async def structured_output(
        self,
        request: ChatRequest,
        response_schema: Any,
        timeout: Optional[float] = None,
    ) -> ChatResponse:
        return await self.chat(request, timeout=timeout)

    async def tool_call(
        self,
        request: ChatRequest,
        timeout: Optional[float] = None,
    ) -> ChatResponse:
        return await self.chat(request, timeout=timeout)
