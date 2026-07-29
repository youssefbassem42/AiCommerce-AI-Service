import logging
from typing import Optional

from app.core.celery_app import celery_app
from app.domain.job.value_objects import JobStatus, JobType
from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository
from app.infrastructure.mongodb.repositories.business_summary_repository import BusinessSummaryRepository
from app.infrastructure.providers.factory import LLMProviderFactory
from app.infrastructure.tasks.helpers import _run_async, complete_job, fail_job, update_job_progress
from app.application.knowledge.generation.service import BusinessSummaryGenerationService
from app.application.knowledge.generation.config import GenerationConfig

logger = logging.getLogger(__name__)


@celery_app.task(
    name="knowledge.generate_summary",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def generate_summary_task(
    self,
    store_id: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    job_id: Optional[str] = None,
) -> dict:
    def _run():
        async def _async_run():
            if job_id:
                await update_job_progress(job_id, 0.1, JobStatus.RUNNING)

            knowledge_repo = KnowledgeRepository()
            summary_repo = BusinessSummaryRepository()
            factory = LLMProviderFactory()
            provider = factory.get_provider("openai")

            service = BusinessSummaryGenerationService(
                knowledge_repository=knowledge_repo,
                summary_repository=summary_repo,
                provider=provider,
            )

            config = GenerationConfig(
                model=model or "gpt-4o-mini",
                temperature=temperature or 0.3,
                max_tokens=max_tokens or 4096,
            )

            if job_id:
                await update_job_progress(job_id, 0.3)

            summary = await service.generate(store_id, config)

            if job_id:
                await update_job_progress(job_id, 1.0)

            result = {
                "id": summary.id,
                "document_id": summary.document_id,
                "version_number": summary.version_number,
                "title": summary.title,
            }

            if job_id:
                await complete_job(job_id, result)

            return result

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        if job_id:
            _run_async(fail_job(job_id, str(exc), self.request.retries, self.max_retries))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)
