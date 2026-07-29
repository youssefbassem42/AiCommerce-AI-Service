from abc import ABC, abstractmethod

from app.domain.knowledge.entities.business_summary import BusinessSummary
from app.shared.kernel.repository import AsyncRepository


class BusinessSummaryRepository(AsyncRepository[BusinessSummary, str], ABC):
    """Domain repository interface for business summaries."""

    @abstractmethod
    async def find_by_document_id(
        self,
        document_id: str,
        version_number: int | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[BusinessSummary]:
        """Find summaries belonging to a document."""
