from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

class ImageURLDTO(BaseModel):
    url: str
    detail: Optional[str] = "auto"

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
    content: Union[str, List[Union[str, Dict[str, Any]]]]
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCallDTO]] = None

class ToolDTO(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema format

class ChatRequest(BaseModel):
    messages: List[MessageDTO]
    model: str
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[List[ToolDTO]] = None
    tool_choice: Optional[str] = None
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

class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str

class EmbeddingResponse(BaseModel):
    model: str
    provider: str
    embeddings: List[List[float]]
    usage: UsageDTO

class ProviderInfoDTO(BaseModel):
    provider: str
    supported_models: List[str]
    capabilities: Dict[str, Any]

class HealthDTO(BaseModel):
    status: str  # "healthy" or "unhealthy"
    provider: str
    latency_ms: float
    details: Optional[str] = None

class StreamingChunkDTO(BaseModel):
    id: str
    model: str
    provider: str
    content: str
    finish_reason: Optional[str] = None
    usage: Optional[UsageDTO] = None

class ErrorDTO(BaseModel):
    message: str
    code: str
    provider: Optional[str] = None
