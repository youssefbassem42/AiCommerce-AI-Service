from fastapi import Depends

from app.application.knowledge.chunking.chunking_service import ChunkingService
from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository
from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository


def get_chunk_repository() -> ChunkRepository:
    return ChunkRepository()


def get_knowledge_repository() -> KnowledgeRepository:
    return KnowledgeRepository()


def get_chunking_service(
    chunk_repository: ChunkRepository = Depends(get_chunk_repository),
    knowledge_repository: KnowledgeRepository = Depends(get_knowledge_repository),
) -> ChunkingService:
    return ChunkingService(
        chunk_repository=chunk_repository,
        knowledge_repository=knowledge_repository,
    )
