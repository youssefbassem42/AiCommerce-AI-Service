from abc import ABC, abstractmethod

from app.domain.job.entities.knowledge_job import KnowledgeJob
from app.domain.job.value_objects import JobStatus, JobType
from app.shared.kernel.repository import AsyncRepository


class JobRepository(AsyncRepository[KnowledgeJob, str], ABC):
    @abstractmethod
    async def find_by_status(
        self,
        status: JobStatus,
        limit: int = 50,
        skip: int = 0,
    ) -> list[KnowledgeJob]:
        pass

    @abstractmethod
    async def find_by_type_and_status(
        self,
        job_type: JobType,
        status: JobStatus,
        limit: int = 50,
        skip: int = 0,
    ) -> list[KnowledgeJob]:
        pass

    @abstractmethod
    async def find_dead_letters(
        self,
        limit: int = 50,
        skip: int = 0,
    ) -> list[KnowledgeJob]:
        pass

    @abstractmethod
    async def update_progress(
        self,
        job_id: str,
        progress: float,
        status: JobStatus | None = None,
    ) -> None:
        pass

    @abstractmethod
    async def mark_completed(
        self,
        job_id: str,
        result: dict | None = None,
    ) -> None:
        pass

    @abstractmethod
    async def mark_failed(
        self,
        job_id: str,
        error_message: str,
        status: JobStatus = JobStatus.FAILED,
    ) -> None:
        pass
