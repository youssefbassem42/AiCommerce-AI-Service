from abc import ABC, abstractmethod

from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument
from app.shared.kernel.repository import AsyncRepository


class KnowledgeRepository(AsyncRepository[KnowledgeDocument, str], ABC):
    """Domain repository interface for knowledge documents."""

    @abstractmethod
    async def find_by_store_id(
        self,
        store_id: str,
        limit: int = 20,
        skip: int = 0,
    ) -> list[KnowledgeDocument]:
        """Find knowledge documents belonging to a store."""

    @abstractmethod
    async def find_by_status(
        self,
        status: str,
        limit: int = 20,
        skip: int = 0,
    ) -> list[KnowledgeDocument]:
        """Find knowledge documents by status."""
