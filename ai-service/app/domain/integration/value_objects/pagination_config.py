from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class PaginationStyle(str, Enum):
    OFFSET = "offset"
    PAGE = "page"
    CURSOR = "cursor"
    NONE = "none"


class PaginationConfig(BaseModel):
    """Pagination configuration derived from API behavior (or user override)."""

    style: PaginationStyle = PaginationStyle.NONE
    page_param: Optional[str] = Field(default=None, max_length=64)
    limit_param: Optional[str] = Field(default=None, max_length=64)
    default_limit: int = Field(default=20, ge=1, le=500)
    cursor_field: Optional[str] = Field(default=None, max_length=128)
    total_field: Optional[str] = Field(default=None, max_length=128)
    next_link_field: Optional[str] = Field(default=None, max_length=128)
