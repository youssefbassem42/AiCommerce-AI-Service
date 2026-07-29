from typing import Any, Optional

from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument
from app.domain.knowledge.repositories.knowledge_repository import KnowledgeRepository as IKnowledgeRepository
from app.infrastructure.mongodb.collections import (
    get_knowledge_chunks_collection,
    get_knowledge_documents_collection,
)
from app.infrastructure.mongodb.documents.knowledge_chunk_document import KnowledgeChunkDocument
from app.infrastructure.mongodb.documents.knowledge_document import KnowledgeDocumentModel
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class KnowledgeRepository(BaseMongoRepository[KnowledgeDocumentModel, KnowledgeDocument], IKnowledgeRepository):
    """MongoDB implementation of the knowledge document repository."""

    def __init__(self):
        super().__init__(get_knowledge_documents_collection(), KnowledgeDocumentModel)
        self.chunks_collection = get_knowledge_chunks_collection()

    async def find_by_id(self, id: str, session: Any = None) -> Optional[KnowledgeDocument]:
        document = await super().find_by_id(id, session=session)
        if document is None:
            return None

        cursor = self.chunks_collection.find({"document_id": id}, session=session).sort("chunk_index", 1)
        chunks = []
        async for data in cursor:
            chunk_doc = KnowledgeChunkDocument.from_mongo_dict(data)
            chunks.append(chunk_doc.to_entity())
        document.chunks = chunks
        return document

    async def find_by_store_id(
        self,
        store_id: str,
        limit: int = 20,
        skip: int = 0,
        session: Any = None,
    ) -> list[KnowledgeDocument]:
        return await self.find_many({"store_id": store_id}, limit=limit, skip=skip, session=session)

    async def find_by_status(
        self,
        status: str,
        limit: int = 20,
        skip: int = 0,
        session: Any = None,
    ) -> list[KnowledgeDocument]:
        return await self.find_many({"status": status}, limit=limit, skip=skip, session=session)
