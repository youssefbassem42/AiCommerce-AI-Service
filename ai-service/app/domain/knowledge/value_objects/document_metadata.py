from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class DocumentMetadata(BaseModel):
    """Document source and classification metadata."""

    source_type: str = Field(default="manual")
    source_uri: Optional[str] = None
    mime_type: Optional[str] = None
    language: str = Field(default="en")
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return [tag.strip() for tag in value if tag and tag.strip()]
