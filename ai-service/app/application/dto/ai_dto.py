from typing import Any

from pydantic import BaseModel


class ImageURLDTO(BaseModel):
    url: str
    detail: str | None = "auto"


class VisionInputDTO(BaseModel):
    type: str = "image_url"
    image_url: ImageURLDTO


class AudioInputDTO(BaseModel):
    data: str  # Base64 encoded audio or path
    format: str  # e.g. "mp3", "wav"


class ToolCallDTO(BaseModel):
    id: str
    type: str = "function"
    function_name: str
    arguments: str  # JSON string of arguments


class MessageDTO(BaseModel):
    role: str  # system, user, assistant, tool, developer
    content: str | list[str | dict[str, Any]]
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCallDTO] | None = None


class ToolDTO(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema format


class ChatRequest(BaseModel):
    messages: list[MessageDTO]
    model: str
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    tools: list[ToolDTO] | None = None
    tool_choice: str | None = None
    json_mode: bool = False


class UsageDTO(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


class ChatResponse(BaseModel):
    id: str
    model: str
    provider: str
    message: MessageDTO
    usage: UsageDTO
    latency_ms: float
    metadata: dict[str, Any] | None = None


class EmbeddingRequest(BaseModel):
    input: str | list[str]
    model: str


class EmbeddingResponse(BaseModel):
    model: str
    provider: str
    embeddings: list[list[float]]
    usage: UsageDTO


class ProviderInfoDTO(BaseModel):
    provider: str
    supported_models: list[str]
    capabilities: dict[str, Any]


class HealthDTO(BaseModel):
    status: str  # "healthy" or "unhealthy"
    provider: str
    latency_ms: float
    details: str | None = None


class StreamingChunkDTO(BaseModel):
    id: str
    model: str
    provider: str
    content: str
    finish_reason: str | None = None
    usage: UsageDTO | None = None


class ErrorDTO(BaseModel):
    message: str
    code: str
    provider: str | None = None
