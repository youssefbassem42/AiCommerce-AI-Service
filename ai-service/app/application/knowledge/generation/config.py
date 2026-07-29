from pydantic import BaseModel, Field


class GenerationConfig(BaseModel):
    model: str = Field(default="gpt-4o-mini", description="LLM model for generation")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: int = Field(default=4096, ge=256, description="Max tokens per response")
    max_document_chars: int = Field(default=100_000, ge=1000, description="Max chars from merged documents")
