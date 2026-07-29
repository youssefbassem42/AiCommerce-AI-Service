import hashlib
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from app.application.knowledge.chunking.chunking_service import (
    ChunkingConfig,
    ChunkingService,
    ChunkingResult,
)
from app.application.knowledge.chunking.config import ChunkingConfig as ChunkConfig
from app.application.knowledge.dto import (
    BusinessSummaryDTO,
    KnowledgeChunkDTO,
    KnowledgeDocumentDTO,
)
from app.application.knowledge.generation.config import GenerationConfig
from app.application.knowledge.generation.service import BusinessSummaryGenerationService
from app.application.knowledge.processing.processor import DocumentProcessor
from app.application.knowledge.services import (
    BusinessSummaryService,
    KnowledgeChunkService,
    KnowledgeDocumentService,
)
from app.core.celery_app import celery_app
from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument
from app.domain.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.domain.knowledge.value_objects import DocumentVersion
from app.domain.knowledge.value_objects.knowledge_version import KnowledgeVersionInfo
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.infrastructure.knowledge.extractors import ExtractorFactory
from app.infrastructure.mongodb.collections import get_knowledge_versions_collection
from app.infrastructure.mongodb.documents.knowledge_version_document import (
    KnowledgeVersionDocument,
)
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.vectorstore.base import VectorRecord, VectorStore

logger = logging.getLogger(__name__)


class SyncReport:
    """Result of a knowledge sync cycle for one store."""

    def __init__(self, tenant: TenantContext) -> None:
        self.tenant = tenant
        self.current_version: int = 0
        self.new_version: int = 0
        self.total_files: int = 0
        self.files_skipped: int = 0
        self.files_processed: int = 0
        self.chunks_generated: int = 0
        self.embeddings_generated: int = 0
        self.summary_updated: bool = False
        self.vectors_synced: bool = False
        self.sync_status: str = "pending"
        self.errors: list[str] = []

    @property
    def version_bumped(self) -> bool:
        return self.new_version > self.current_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.tenant.organization_id,
            "store_id": self.tenant.store_id,
            "store_slug": self.tenant.store_slug,
            "current_version": self.current_version,
            "new_version": self.new_version,
            "version_bumped": self.version_bumped,
            "total_files": self.total_files,
            "files_skipped": self.files_skipped,
            "files_processed": self.files_processed,
            "chunks_generated": self.chunks_generated,
            "embeddings_generated": self.embeddings_generated,
            "summary_updated": self.summary_updated,
            "vectors_synced": self.vectors_synced,
            "sync_status": self.sync_status,
            "errors": self.errors,
        }


class KnowledgeSyncCoordinator:
    """Orchestrates knowledge synchronization for a single store tenant.

    Detects document changes via checksum comparison, invalidates stale
    data, enqueues background jobs, and manages knowledge version tracking.
    Delegates all processing to existing services — never implements
    extraction, chunking, embedding, or summary logic directly.
    """

    def __init__(
        self,
        tenant: TenantContext,
        document_service: KnowledgeDocumentService,
        chunk_service: KnowledgeChunkService,
        summary_service: BusinessSummaryService,
        knowledge_repository: KnowledgeRepository,
        extractor_factory: Optional[ExtractorFactory] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        self.tenant = tenant
        self.document_service = document_service
        self.chunk_service = chunk_service
        self.summary_service = summary_service
        self.knowledge_repository = knowledge_repository
        self.extractor_factory = extractor_factory or ExtractorFactory()
        self.llm_provider = llm_provider
        self.vector_store = vector_store

    async def run_sync(
        self,
        file_paths: Optional[list[str]] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        chunk_strategy: str = "recursive",
        summary_model: str = "gpt-4o-mini",
        enqueue_background: bool = True,
    ) -> SyncReport:
        report = SyncReport(self.tenant)

        current_version = await self._load_current_version()
        report.current_version = current_version

        docs = await self.knowledge_repository.find_by_store_id(
            self.tenant.store_id, limit=1000
        )
        report.total_files = len(docs)

        changed_docs: list[KnowledgeDocument] = []
        for doc in docs:
            if await self._document_changed(doc):
                changed_docs.append(doc)
            else:
                report.files_skipped += 1

        report.files_processed = len(changed_docs)

        if not changed_docs:
            report.sync_status = "no_changes"
            logger.info(
                "Store '%s': no document changes detected (v%d), skipping sync",
                self.tenant.store_slug, current_version,
            )
            return report

        version_vo = await self._start_version(current_version)
        report.new_version = version_vo.version_number

        chunk_config = ChunkConfig(
            chunk_size=chunk_size,
            overlap=chunk_overlap,
            strategy=chunk_strategy,
        )

        total_chunks = 0

        for doc in changed_docs:
            await self._invalidate_document_data(doc)

            if enqueue_background:
                self._enqueue_extract(doc.id, doc.source_url or "")
                self._enqueue_chunk(doc.id, chunk_config)
                self._enqueue_embed(doc.id)
                self._enqueue_vector_sync(self.tenant.store_id)
            else:
                doc = await self._process_document(doc)
                chunk_result = await self._chunk_document(doc, chunk_config)
                total_chunks += chunk_result.chunk_count

        report.chunks_generated = total_chunks

        if changed_docs and not enqueue_background:
            if self.llm_provider and self.vector_store:
                await self._generate_embeddings_and_sync(changed_docs)
                report.embeddings_generated = total_chunks
                report.vectors_synced = True

            await self._regenerate_summary(summary_model)
            report.summary_updated = True
        elif changed_docs:
            self._enqueue_summary(self.tenant.store_id, summary_model)
            self._enqueue_bump_version(self.tenant.store_id, version_vo.version_number)

        await self._complete_version(version_vo, report)
        report.sync_status = "completed"

        logger.info(
            "Store '%s' sync complete: v%d -> v%d, %d processed, %d skipped, %d chunks",
            self.tenant.store_slug,
            report.current_version,
            report.new_version,
            report.files_processed,
            report.files_skipped,
            report.chunks_generated,
        )
        return report

    async def _document_changed(self, doc: KnowledgeDocument) -> bool:
        if not doc.versions:
            return True
        latest = max(doc.versions, key=lambda v: v.version_number)
        if not latest.checksum:
            return True
        stored = getattr(doc.metadata.attributes, "source_checksum", None) or ""
        if stored and stored == latest.checksum:
            return False
        return True

    async def _compute_checksum(self, file_path: str) -> str:
        sha = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for block in iter(lambda: f.read(65536), b""):
                    sha.update(block)
            return sha.hexdigest()
        except (FileNotFoundError, OSError):
            return ""

    async def _invalidate_document_data(self, doc: KnowledgeDocument) -> None:
        existing = await self.knowledge_repository.find_by_id(doc.id)
        if existing:
            existing.status = "invalidated"
            existing.updated_at = datetime.now(UTC)
            await self.knowledge_repository.update(existing)

    async def _process_document(self, doc: KnowledgeDocument) -> KnowledgeDocument:
        pipeline = DocumentProcessor(
            repository=self.knowledge_repository,
            extractor_factory=self.extractor_factory,
        )
        return await pipeline.process(doc, doc.source_url or "")

    async def _chunk_document(
        self, doc: KnowledgeDocument, config: ChunkConfig
    ) -> ChunkingResult:
        repo = self.knowledge_repository
        from app.domain.knowledge.repositories.chunk_repository import ChunkRepository
        chunk_repo = ChunkRepository()
        service = ChunkingService(
            chunk_repository=chunk_repo,
            knowledge_repository=repo,
        )
        return await service.chunk_document(doc, config)

    async def _generate_embeddings_and_sync(
        self, docs: list[KnowledgeDocument]
    ) -> None:
        if not self.llm_provider or not self.vector_store:
            logger.warning("Missing llm_provider or vector_store, skipping embedding sync")
            return
        from app.application.dto.ai_dto import EmbeddingRequest

        collection = self.tenant.collection_name
        all_points: list[VectorRecord] = []

        from app.domain.knowledge.repositories.chunk_repository import ChunkRepository
        chunk_repo = ChunkRepository()

        for doc in docs:
            chunks = await chunk_repo.find_by_document_id(
                doc.id, version_number=doc.current_version, limit=10_000
            )
            if not chunks:
                continue
            texts = [c.content for c in chunks]
            try:
                request = EmbeddingRequest(input=texts, model="gemini-embedding-001")
                response = await self.llm_provider.embeddings(request)
                for chunk, emb in zip(chunks, response.embeddings):
                    all_points.append(VectorRecord(
                        id=chunk.id,
                        vector=emb,
                        payload={
                            "organization_id": self.tenant.organization_id,
                            "store_id": self.tenant.store_id,
                            "merchant_id": self.tenant.merchant_id,
                            "document_id": chunk.document_id,
                            "chunk_id": chunk.id,
                            "knowledge_version": self.tenant.knowledge_version,
                            "document_status": doc.status if hasattr(doc, 'status') else "active",
                            "document_type": doc.metadata.source_type,
                            "source_type": doc.metadata.source_type,
                            "language": doc.language,
                            "product_id": doc.metadata.attributes.get("product_id", ""),
                            "category_id": doc.metadata.attributes.get("category_id", ""),
                            "brand_id": doc.metadata.attributes.get("brand_id", ""),
                        },
                    ))
            except Exception as e:
                logger.error("Embedding generation failed for doc '%s': %s", doc.id, e)

        if all_points:
            await self.vector_store.upsert(collection, all_points)
            logger.info("Synced %d vectors to '%s'", len(all_points), collection)

    async def _regenerate_summary(self, model: str) -> None:
        if not self.llm_provider:
            return
        from app.domain.knowledge.repositories.business_summary_repository import (
            BusinessSummaryRepository,
        )
        gen_service = BusinessSummaryGenerationService(
            knowledge_repository=self.knowledge_repository,
            summary_repository=BusinessSummaryRepository(),
            provider=self.llm_provider,
        )
        config = GenerationConfig(model=model)
        await gen_service.generate(self.tenant.store_id, config)

    async def _load_current_version(self) -> int:
        col = get_knowledge_versions_collection()
        cursor = col.find(
            {"organization_id": self.tenant.organization_id, "store_id": self.tenant.store_id},
        ).sort("version_number", -1).limit(1)
        latest = await cursor.to_list(length=1)
        if latest:
            doc = KnowledgeVersionDocument.from_mongo_dict(latest[0])
            return doc.version_number
        return 0

    async def _start_version(self, current: int) -> KnowledgeVersionInfo:
        col = get_knowledge_versions_collection()
        for prev_status in ["active"]:
            await col.update_many(
                {
                    "organization_id": self.tenant.organization_id,
                    "store_id": self.tenant.store_id,
                    "status": prev_status,
                },
                {"$set": {"status": "previous"}},
            )
        vo = KnowledgeVersionInfo(
            organization_id=self.tenant.organization_id,
            store_id=self.tenant.store_id,
            version_number=current + 1,
            previous_version=current,
            status="active",
            started_at=datetime.now(UTC),
        )
        doc = KnowledgeVersionDocument.from_value_object(vo)
        await col.insert_one(doc.to_mongo_dict())
        return vo

    async def _complete_version(
        self, vo: KnowledgeVersionInfo, report: SyncReport
    ) -> None:
        col = get_knowledge_versions_collection()
        await col.update_one(
            {
                "organization_id": self.tenant.organization_id,
                "store_id": self.tenant.store_id,
                "version_number": vo.version_number,
            },
            {
                "$set": {
                    "completed_at": datetime.now(UTC),
                    "document_count": report.total_files,
                    "chunk_count": report.chunks_generated,
                    "files_processed": report.files_processed,
                    "files_skipped": report.files_skipped,
                    "total_files": report.total_files,
                    "summary_generated": report.summary_updated,
                    "embeddings_generated": report.embeddings_generated,
                    "vectors_synced": report.vectors_synced,
                }
            },
        )

    def _enqueue_extract(self, doc_id: str, file_path: str) -> None:
        celery_app.send_task(
            "kb.extract_document",
            args=[doc_id, file_path, self.tenant.organization_id, self.tenant.store_id],
        )

    def _enqueue_chunk(self, doc_id: str, config: Any) -> None:
        celery_app.send_task(
            "kb.chunk_document",
            args=[doc_id, config.model_dump(), self.tenant.organization_id, self.tenant.store_id],
        )

    def _enqueue_embed(self, doc_id: str) -> None:
        celery_app.send_task(
            "kb.embed_chunks",
            args=[doc_id, self.tenant.organization_id, self.tenant.store_id],
        )

    def _enqueue_vector_sync(self, store_id: str) -> None:
        celery_app.send_task(
            "kb.sync_vector_db",
            args=[store_id, self.tenant.organization_id, self.tenant.store_id],
        )

    def _enqueue_summary(self, store_id: str, model: str) -> None:
        celery_app.send_task(
            "kb.generate_summary",
            args=[store_id, model, self.tenant.organization_id, self.tenant.store_id],
        )

    def _enqueue_bump_version(self, store_id: str, version: int) -> None:
        celery_app.send_task(
            "kb.bump_version",
            args=[store_id, version, self.tenant.organization_id, self.tenant.store_id],
        )
