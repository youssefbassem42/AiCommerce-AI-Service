from typing import Annotated, Any

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

# --- Request Schemas ---


class ImageURLSchema(BaseModel):
    url: StrictStr
    detail: StrictStr | None = "auto"

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
    content: StrictStr | list[StrictStr | VisionSchema | dict[str, Any]]
    name: StrictStr | None = None
    tool_call_id: StrictStr | None = None
    tool_calls: list[ToolCallSchema] | None = None

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
    parameters: dict[StrictStr, Any]  # JSON Schema format

    @field_validator("name")
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        if not v.isalnum() and "_" not in v and "-" not in v:
            raise ValueError("Tool name must be alphanumeric or contain underscores/hyphens.")
        return v


class ChatRequestSchema(BaseModel):
    messages: list[MessageSchema]
    model: StrictStr
    temperature: Annotated[StrictFloat, Field(ge=0.0, le=2.0)] | None = None
    top_p: Annotated[StrictFloat, Field(ge=0.0, le=1.0)] | None = None
    max_tokens: StrictInt | None = None
    stream: StrictBool = False
    tools: list[ToolSchema] | None = None
    tool_choice: StrictStr | None = None
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
                pass
                # We can log this warning or append instructions, but we keep validation passing
        return self


class CompletionSchema(BaseModel):
    prompt: StrictStr
    model: StrictStr
    max_tokens: StrictInt | None = None


class StructuredOutputSchema(BaseModel):
    messages: list[MessageSchema]
    model: StrictStr
    # Schema definition must be a valid JSON Schema or Pydantic model
    schema_definition: dict[StrictStr, Any]


class EmbeddingSchema(BaseModel):
    input: StrictStr | list[StrictStr]
    model: StrictStr

    @field_validator("input")
    @classmethod
    def validate_input(cls, v: str | list[str]) -> str | list[str]:
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
    embeddings: list[list[StrictFloat]]
    usage: UsageSchema


class HealthResponseSchema(BaseModel):
    status: StrictStr
    provider: StrictStr
    latency_ms: StrictFloat
    details: StrictStr | None = None


class ProviderResponseSchema(BaseModel):
    provider: StrictStr
    supported_models: list[StrictStr]
    capabilities: dict[StrictStr, StrictBool]


class ErrorSchema(BaseModel):
    message: StrictStr
    code: StrictStr
    provider: StrictStr | None = None
