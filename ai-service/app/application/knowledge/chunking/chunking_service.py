import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.application.knowledge.chunking.config import ChunkingConfig
from app.application.knowledge.chunking.strategies import get_chunker
from app.domain.knowledge.entities.knowledge_chunk import KnowledgeChunk
from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument
from app.domain.knowledge.exceptions import ChunkingException
from app.domain.knowledge.repositories.chunk_repository import ChunkRepository
from app.domain.knowledge.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)


@dataclass
class ChunkingResult:
    document_id: str
    strategy: str
    chunk_size: int
    overlap: int
    chunk_count: int
    chunks: list[KnowledgeChunk] = field(default_factory=list)


class ChunkingService:
    def __init__(
        self,
        chunk_repository: ChunkRepository,
        knowledge_repository: KnowledgeRepository,
    ):
        self.chunk_repository = chunk_repository
        self.knowledge_repository = knowledge_repository

    async def chunk_document(
        self,
        document: KnowledgeDocument,
        config: ChunkingConfig | None = None,
    ) -> ChunkingResult:
        config = config or ChunkingConfig()

        text = document.processed_text
        if not text:
            raise ChunkingException(
                f"Document '{document.id}' has no processed_text. Run document processing first."
            )

        chunker = get_chunker(config.strategy)
        raw_chunks = chunker.chunk(text, config)

        if not raw_chunks:
            raise ChunkingException(
                f"Chunking produced zero chunks for document '{document.id}'"
            )

        chunks = await self._delete_and_recreate(document, raw_chunks, config, chunker.strategy_name)

        document.status = "active"
        document.chunking_strategy = config.strategy
        document.updated_at = datetime.now(UTC)
        await self.knowledge_repository.update(document)

        logger.info(
            "Document '%s' chunked into %d chunks (strategy=%s, size=%d, overlap=%d)",
            document.id, len(chunks), config.strategy, config.chunk_size, config.overlap,
        )

        return ChunkingResult(
            document_id=document.id,
            strategy=config.strategy,
            chunk_size=config.chunk_size,
            overlap=config.overlap,
            chunk_count=len(chunks),
            chunks=chunks,
        )

    async def _delete_and_recreate(
        self,
        document: KnowledgeDocument,
        raw_chunks: list[str],
        config: ChunkingConfig,
        strategy_name: str,
    ) -> list[KnowledgeChunk]:
        existing = await self.chunk_repository.find_by_document_id(
            document.id, version_number=document.current_version, limit=10_000
        )
        for old in existing:
            await self.chunk_repository.delete(old.id)

        entities = self._build_chunks(document, raw_chunks, config, strategy_name)

        inserted = await self.chunk_repository.bulk_insert(entities)
        if inserted != len(entities):
            logger.warning(
                "Expected %d chunks, inserted %d for document '%s'",
                len(entities), inserted, document.id,
            )
        return entities

    def _build_chunks(
        self,
        document: KnowledgeDocument,
        raw_chunks: list[str],
        config: ChunkingConfig,
        strategy_name: str,
    ) -> list[KnowledgeChunk]:
        entities = []
        for idx, text in enumerate(raw_chunks):
            tokens = self._count_tokens(text)
            title = self._derive_title(document, text, idx, raw_chunks)
            chunk = KnowledgeChunk(
                id=str(ObjectId()),
                document_id=document.id,
                version_number=document.current_version,
                chunk_index=idx,
                title=title,
                content=text,
                metadata={
                    "strategy": strategy_name,
                    "chunk_size": config.chunk_size,
                    "overlap": config.overlap,
                    "language": document.language,
                    "estimated_tokens": tokens,
                    "parent_document_id": document.id,
                    "parent_title": document.title,
                    "chunk_number": idx + 1,
                },
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            entities.append(chunk)
        return entities

    def _count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    def _derive_title(self, document: KnowledgeDocument, chunk_text: str, idx: int, all_chunks: list[str]) -> str | None:
        if idx == 0:
            return document.title
        lines = [l.strip() for l in chunk_text.split("\n") if l.strip()]
        for line in lines[:5]:
            line = line.rstrip(".:!?")
            if len(line) > 10 and len(line) < 200:
                return line
        return f"{document.title} — part {idx + 1}"
