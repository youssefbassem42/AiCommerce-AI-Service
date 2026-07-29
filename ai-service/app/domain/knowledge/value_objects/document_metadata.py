from typing import Any

from pydantic import BaseModel, Field, field_validator


class DocumentMetadata(BaseModel):
    """Document source and classification metadata."""

    source_type: str = Field(default="manual")
    source_uri: str | None = None
    mime_type: str | None = None
    language: str = Field(default="en")
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return [tag.strip() for tag in value if tag and tag.strip()]
