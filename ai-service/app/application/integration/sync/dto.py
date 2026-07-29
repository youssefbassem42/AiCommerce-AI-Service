from datetime import datetime

from pydantic import BaseModel, Field


class EntitySyncResultDTO(BaseModel):
    entity_type: str
    total_fetched: int = 0
    total_mapped: int = 0
    total_upserted: int = 0
    errors: list[str] = Field(default_factory=list)


class SyncResultDTO(BaseModel):
    connection_id: str
    store_id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"
    entity_results: list[EntitySyncResultDTO] = Field(default_factory=list)
    total_duration_seconds: float | None = None
    error: str | None = None
