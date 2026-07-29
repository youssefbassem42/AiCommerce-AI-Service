from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import Field

from app.domain.integration.exceptions import IntegrationValidationException
from app.shared.kernel.aggregate_root import AggregateRoot


class DataEntity(AggregateRoot[str]):
    """Schema-agnostic domain entity for any platform entity type.

    Stores the full payload from any external schema in the flexible ``data``
    dict, preserving every field the source returns — no canonical model needed.
    """

    store_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1, max_length=128)
    external_id: str = Field(..., min_length=1)
    data: dict[str, Any] = Field(default_factory=dict)
    connection_id: Optional[str] = None
    synced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = None

    def update_data(self, new_data: dict[str, Any]) -> None:
        if not isinstance(new_data, dict):
            raise IntegrationValidationException("Data must be a dictionary.")
        self.data = new_data
        self.updated_at = datetime.now(UTC)
