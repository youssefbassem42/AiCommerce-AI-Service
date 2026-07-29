from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobResponseSchema(BaseModel):
    id: str
    job_type: str
    status: str
    progress: float
    payload: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int
    max_retries: int
    store_id: Optional[str] = None
    organization_id: Optional[str] = None
    triggered_by: Optional[str] = None
    celery_task_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
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
