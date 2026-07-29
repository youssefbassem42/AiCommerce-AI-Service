from typing import Optional

from pydantic import BaseModel, Field


class ProcessingStats(BaseModel):
    page_count: Optional[int] = Field(default=None, ge=0)
    word_count: int = Field(default=0, ge=0)
    char_count: int = Field(default=0, ge=0)
    estimated_tokens: int = Field(default=0, ge=0)
    line_count: int = Field(default=0, ge=0)
    detected_language: Optional[str] = None
    language_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
