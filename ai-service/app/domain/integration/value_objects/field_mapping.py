from typing import Any, Optional

from pydantic import BaseModel, Field


class FieldMapping(BaseModel):
    """Maps a single source field (dot notation supported) to a canonical target field."""

    source: str = Field(..., min_length=1, max_length=256)
    target: str = Field(..., min_length=1, max_length=128)
    transformer: Optional[str] = Field(default=None, max_length=64)
    default_value: Any = None
    required: bool = False
