from app.domain.knowledge.entities.knowledge_chunk import KnowledgeChunk
from app.domain.knowledge.repositories.chunk_repository import ChunkRepository as IChunkRepository
from app.infrastructure.mongodb.collections import get_knowledge_chunks_collection
from app.infrastructure.mongodb.documents.knowledge_chunk_document import KnowledgeChunkDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class ChunkRepository(BaseMongoRepository[KnowledgeChunkDocument, KnowledgeChunk], IChunkRepository):
    """MongoDB implementation of the knowledge chunk repository."""

    def __init__(self):
        super().__init__(get_knowledge_chunks_collection(), KnowledgeChunkDocument)

    async def find_by_document_id(
        self,
        document_id: str,
        version_number: int | None = None,
        limit: int = 100,
        skip: int = 0,
        session=None,
    ) -> list[KnowledgeChunk]:
        filters: dict[str, str | int] = {"document_id": document_id}
        if version_number is not None:
            filters["version_number"] = version_number
        return await self.find_many(filters=filters, limit=limit, skip=skip, session=session)
