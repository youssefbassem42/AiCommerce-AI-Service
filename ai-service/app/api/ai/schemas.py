from typing import Any, Dict, List, Optional, Union
from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)
from typing_extensions import Annotated

# --- Request Schemas ---

class ImageURLSchema(BaseModel):
    url: StrictStr
    detail: Optional[StrictStr] = "auto"

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith("http://") and not v.startswith("https://") and not v.startswith("data:image/"):
            raise ValueError("URL must start with http://, https://, or be a valid base64 data URI.")
        return v

class VisionSchema(BaseModel):
    type: StrictStr = "image_url"
    image_url: ImageURLSchema

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v != "image_url":
            raise ValueError("Vision type must be 'image_url'")
        return v

class ToolCallSchema(BaseModel):
    id: StrictStr
    type: StrictStr = "function"
    function_name: StrictStr
    arguments: StrictStr

class MessageSchema(BaseModel):
    role: StrictStr  # system, developer, user, assistant, tool
    content: Union[StrictStr, List[Union[StrictStr, VisionSchema, Dict[str, Any]]]]
    name: Optional[StrictStr] = None
    tool_call_id: Optional[StrictStr] = None
    tool_calls: Optional[List[ToolCallSchema]] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = {"system", "developer", "user", "assistant", "tool"}
        if v not in valid_roles:
            raise ValueError(f"Role must be one of {valid_roles}")
        return v

class ToolSchema(BaseModel):
    name: StrictStr
    description: StrictStr
    parameters: Dict[StrictStr, Any]  # JSON Schema format

    @field_validator("name")
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        if not v.isalnum() and "_" not in v and "-" not in v:
            raise ValueError("Tool name must be alphanumeric or contain underscores/hyphens.")
        return v

class ChatRequestSchema(BaseModel):
    messages: List[MessageSchema]
    model: StrictStr
    temperature: Optional[Annotated[StrictFloat, Field(ge=0.0, le=2.0)]] = None
    top_p: Optional[Annotated[StrictFloat, Field(ge=0.0, le=1.0)]] = None
    max_tokens: Optional[StrictInt] = None
    stream: StrictBool = False
    tools: Optional[List[ToolSchema]] = None
    tool_choice: Optional[StrictStr] = None
    json_mode: StrictBool = False

    @model_validator(mode="after")
    def validate_json_mode_requires_instructions(self) -> "ChatRequestSchema":
        if self.json_mode:
            # Simple validation check: ensure there is system/user guidance to output JSON
            has_json_instruction = False
            for msg in self.messages:
                content_str = str(msg.content).lower()
                if "json" in content_str:
                    has_json_instruction = True
                    break
            if not has_json_instruction:
                logger_warning = "JSON mode is enabled but no messages explicitly prompt for JSON output."
                # We can log this warning or append instructions, but we keep validation passing
        return self

class CompletionSchema(BaseModel):
    prompt: StrictStr
    model: StrictStr
    max_tokens: Optional[StrictInt] = None

class StructuredOutputSchema(BaseModel):
    messages: List[MessageSchema]
    model: StrictStr
    # Schema definition must be a valid JSON Schema or Pydantic model
    schema_definition: Dict[StrictStr, Any]

class EmbeddingSchema(BaseModel):
    input: Union[StrictStr, List[StrictStr]]
    model: StrictStr

    @field_validator("input")
    @classmethod
    def validate_input(cls, v: Union[str, List[str]]) -> Union[str, List[str]]:
        if isinstance(v, list) and len(v) == 0:
            raise ValueError("Embedding input list cannot be empty.")
        if isinstance(v, str) and len(v.strip()) == 0:
            raise ValueError("Embedding input string cannot be empty.")
        return v

class HealthSchema(BaseModel):
    provider: StrictStr

class ProviderSchema(BaseModel):
    name: StrictStr

class StreamingSchema(ChatRequestSchema):
    # Stream is forced to true
    stream: StrictBool = True

# --- Response Schemas ---

class UsageSchema(BaseModel):
    prompt_tokens: StrictInt
    completion_tokens: StrictInt
    total_tokens: StrictInt
    cost: StrictFloat

class ChatResponseSchema(BaseModel):
    id: StrictStr
    model: StrictStr
    provider: StrictStr
    message: MessageSchema
    usage: UsageSchema
    latency_ms: StrictFloat

class EmbeddingResponseSchema(BaseModel):
    model: StrictStr
    provider: StrictStr
    embeddings: List[List[StrictFloat]]
    usage: UsageSchema

class HealthResponseSchema(BaseModel):
    status: StrictStr
    provider: StrictStr
    latency_ms: StrictFloat
    details: Optional[StrictStr] = None

class ProviderResponseSchema(BaseModel):
    provider: StrictStr
    supported_models: List[StrictStr]
    capabilities: Dict[StrictStr, StrictBool]

class ErrorSchema(BaseModel):
    message: StrictStr
    code: StrictStr
    provider: Optional[StrictStr] = None
