from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig


class EntityMapping(BaseModel):
    """Configuration that maps a single canonical entity to its list/detail endpoints."""

    entity_type: str = Field(..., min_length=1, max_length=64)
    list_path: Optional[str] = Field(default=None, max_length=512)
    list_method: str = Field(default="GET", min_length=3, max_length=10)
    detail_path: Optional[str] = Field(default=None, max_length=512)
    detail_method: str = Field(default="GET", min_length=3, max_length=10)
    id_field: str = Field(..., min_length=1, max_length=128)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    field_mappings: list[FieldMapping] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_paths(self) -> "EntityMapping":
        if not self.list_path and not self.detail_path:
            raise ValueError("EntityMapping requires at least one of list_path or detail_path.")
        return self
