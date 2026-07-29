from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobResponseSchema(BaseModel):
    id: str
    job_type: str
    status: str
    progress: float
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    error_message: str | None = None
    retry_count: int
    max_retries: int
    store_id: str | None = None
    organization_id: str | None = None
    triggered_by: str | None = None
    celery_task_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedJobResponseSchema(BaseModel):
    items: list[JobResponseSchema]
    total: int
    page: int
    page_size: int


class JobCreateResponseSchema(BaseModel):
    job_id: str
    job_type: str
    status: str
    message: str
