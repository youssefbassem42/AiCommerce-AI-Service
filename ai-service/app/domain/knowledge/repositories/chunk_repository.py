from abc import ABC, abstractmethod

from app.domain.knowledge.entities.knowledge_chunk import KnowledgeChunk
from app.shared.kernel.repository import AsyncRepository


class ChunkRepository(AsyncRepository[KnowledgeChunk, str], ABC):
    """Domain repository interface for knowledge chunks."""

    @abstractmethod
    async def find_by_document_id(
        self,
        document_id: str,
        version_number: int | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[KnowledgeChunk]:
        """Find chunks belonging to a document."""
