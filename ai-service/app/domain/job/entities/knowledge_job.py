from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.domain.job.value_objects import JobStatus, JobType
from app.shared.kernel.entity import Entity


class KnowledgeJob(Entity[str]):
    job_type: JobType
    status: JobStatus = Field(default=JobStatus.PENDING)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = Field(default=None)
    error_message: str | None = Field(default=None)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    store_id: str | None = Field(default=None)
    organization_id: str | None = Field(default=None)
    triggered_by: str | None = Field(default=None)
    celery_task_id: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
