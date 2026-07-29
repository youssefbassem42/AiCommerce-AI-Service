from pydantic import BaseModel, Field


class ProcessingStats(BaseModel):
    page_count: int | None = Field(default=None, ge=0)
    word_count: int = Field(default=0, ge=0)
    char_count: int = Field(default=0, ge=0)
    estimated_tokens: int = Field(default=0, ge=0)
    line_count: int = Field(default=0, ge=0)
    detected_language: str | None = None
    language_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
