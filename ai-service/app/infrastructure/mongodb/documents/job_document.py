from datetime import datetime
from typing import Any, Optional

from pydantic import Field

from app.domain.job.entities.knowledge_job import KnowledgeJob
from app.domain.job.value_objects import JobStatus, JobType
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class KnowledgeJobDocument(BaseMongoDocument):
    job_type: str = Field(...)
    status: str = Field(default="pending")
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    store_id: Optional[str] = Field(default=None)
    organization_id: Optional[str] = Field(default=None)
    triggered_by: Optional[str] = Field(default=None)
    celery_task_id: Optional[str] = Field(default=None, index=True)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    def to_entity(self) -> KnowledgeJob:
        return KnowledgeJob(
            id=str(self.id),
            job_type=JobType(self.job_type),
            status=JobStatus(self.status),
            progress=self.progress,
            payload=self.payload,
            result=self.result,
            error_message=self.error_message,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            store_id=self.store_id,
            organization_id=self.organization_id,
            triggered_by=self.triggered_by,
            celery_task_id=self.celery_task_id,
            started_at=self.started_at,
            completed_at=self.completed_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: KnowledgeJob) -> "KnowledgeJobDocument":
        return cls(
            _id=entity.id,
            job_type=entity.job_type.value,
            status=entity.status.value,
            progress=entity.progress,
            payload=entity.payload,
            result=entity.result,
            error_message=entity.error_message,
            retry_count=entity.retry_count,
            max_retries=entity.max_retries,
            store_id=entity.store_id,
            organization_id=entity.organization_id,
            triggered_by=entity.triggered_by,
            celery_task_id=entity.celery_task_id,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
