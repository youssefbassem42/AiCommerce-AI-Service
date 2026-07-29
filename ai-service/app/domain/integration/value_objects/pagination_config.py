from enum import StrEnum

from pydantic import BaseModel, Field


class PaginationStyle(StrEnum):
    OFFSET = "offset"
    PAGE = "page"
    CURSOR = "cursor"
    NONE = "none"


class PaginationConfig(BaseModel):
    """Pagination configuration derived from API behavior (or user override)."""

    style: PaginationStyle = PaginationStyle.NONE
    page_param: str | None = Field(default=None, max_length=64)
    limit_param: str | None = Field(default=None, max_length=64)
    default_limit: int = Field(default=20, ge=1, le=500)
    cursor_field: str | None = Field(default=None, max_length=128)
    total_field: str | None = Field(default=None, max_length=128)
    next_link_field: str | None = Field(default=None, max_length=128)
