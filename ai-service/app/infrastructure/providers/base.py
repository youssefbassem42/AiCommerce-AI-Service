from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, List, Optional

from app.application.dto.ai_dto import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    HealthDTO,
    StreamingChunkDTO,
)


class BaseLLMProvider(ABC):
    """Abstract interface for all LLM providers. Every provider must implement all methods."""

    @abstractmethod
    async def chat(self, request: ChatRequest, timeout: Optional[float] = None) -> ChatResponse: ...

    @abstractmethod
    async def stream(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> AsyncGenerator[StreamingChunkDTO, None]: ...

    @abstractmethod
    async def embeddings(
        self, request: EmbeddingRequest, timeout: Optional[float] = None
    ) -> EmbeddingResponse: ...

    @abstractmethod
    async def health_check(self) -> HealthDTO: ...

    @abstractmethod
    async def list_models(self) -> List[str]: ...

    @abstractmethod
    async def structured_output(
        self, request: ChatRequest, response_schema: Any, timeout: Optional[float] = None
    ) -> ChatResponse: ...

    @abstractmethod
    async def tool_call(self, request: ChatRequest, timeout: Optional[float] = None) -> ChatResponse: ...
