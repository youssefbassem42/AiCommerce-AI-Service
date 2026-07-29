import asyncio
import os
import logging
from typing import Any, Optional

from app.application.knowledge.retrieval import RetrieverService
from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.application.knowledge.retrieval.dto import RetrievedChunkDTO, UnifiedRetrievalResult
from app.application.rag.dedup import deduplicate_chunks
from app.domain.knowledge.repositories.business_summary_repository import (
    BusinessSummaryRepository,
)
from app.domain.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.domain.knowledge.value_objects.knowledge_version import KnowledgeVersionInfo
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.infrastructure.mongodb.collections import get_knowledge_versions_collection
from app.infrastructure.mongodb.documents.knowledge_version_document import (
    KnowledgeVersionDocument,
)

logger = logging.getLogger(__name__)


class BuiltContext:
    """Aggregated RAG context assembled by ContextBuilder."""

    def __init__(self) -> None:
        self.business_summary: Optional[str] = None
        self.business_summary_version: Optional[int] = None
        self.business_summary_sections: dict[str, str] = {}
        self.chunks: list[RetrievedChunkDTO] = []
        self.knowledge_version: Optional[KnowledgeVersionInfo] = None
        self.active_version_number: int = 0
        self.merchant_profile: Optional[str] = None
        self.store_info: Optional[str] = None
        self.product_context: Optional[str] = None
        self.categories: list[str] = []
        self.brands: list[str] = []
        self.collections: list[str] = []
        self.policies: list[str] = []
        self.faqs: list[str] = []
        self.tenant: Optional[TenantContext] = None
        self.latency_ms: float = 0.0
        self.total_chunks_retrieved: int = 0

    def has_context(self) -> bool:
        return bool(self.business_summary or self.chunks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "business_summary": self.business_summary,
            "business_summary_version": self.business_summary_version,
            "business_summary_sections": self.business_summary_sections,
            "chunks": [c.model_dump() for c in self.chunks],
            "knowledge_version": self.active_version_number,
            "merchant_profile": self.merchant_profile,
            "store_info": self.store_info,
            "product_context": self.product_context,
            "categories": self.categories,
            "brands": self.brands,
            "collections": self.collections,
            "policies": self.policies,
            "faqs": self.faqs,
            "tenant": self.tenant.model_dump() if self.tenant else None,
            "latency_ms": self.latency_ms,
            "total_chunks_retrieved": self.total_chunks_retrieved,
        }


class ContextBuilder:
    """Assembles the complete RAG context for a tenant.

    Loads the active business summary, retrieves relevant knowledge chunks,
    and merges all available commerce entity data (products, categories,
    brands, policies, FAQs, etc.) into a single optimised context.

    Every source is scoped to the current tenant — no global data is loaded.
    """

    def __init__(
        self,
        tenant: TenantContext,
        retriever: RetrieverService,
        knowledge_repository: KnowledgeRepository,
        business_summary_repository: BusinessSummaryRepository,
    ) -> None:
        self._tenant = tenant
        self._retriever = retriever
        self._knowledge_repo = knowledge_repository
        self._summary_repo = business_summary_repository
        self._conf = RetrievalConfig(
            top_k=10,
            score_threshold=0.0,
            use_hybrid=True,
            use_mmr=True,
            rerank=False,
            embedding_model=os.getenv("RAG_EMBEDDING_MODEL", "gemini-embedding-001"),
        )

    @property
    def tenant(self) -> TenantContext:
        return self._tenant

    async def build(self, query: str) -> BuiltContext:
        import time
        start = time.perf_counter()

        ctx = BuiltContext()
        ctx.tenant = self._tenant

        results = await asyncio.gather(
            self._load_business_summary(),
            self._retrieve_chunks(query),
            self._load_knowledge_version(),
            return_exceptions=True,
        )

        for res in results:
            if isinstance(res, Exception):
                logger.warning("ContextBuilder source failed: %s", res)

        ctx.business_summary = _safe_get(results, 0, {}).get("summary")
        ctx.business_summary_version = _safe_get(results, 0, {}).get("version")
        ctx.business_summary_sections = _safe_get(results, 0, {}).get("sections", {})

        retrieval: Optional[UnifiedRetrievalResult] = _safe_get(results, 1)
        if isinstance(retrieval, UnifiedRetrievalResult):
            ctx.chunks = deduplicate_chunks(retrieval.results)
            ctx.total_chunks_retrieved = retrieval.total_count

        ctx.knowledge_version = _safe_get(results, 2)
        ctx.active_version_number = (
            ctx.knowledge_version.version_number if ctx.knowledge_version else 0
        )

        await self.add_merchant_profile(ctx)
        await self.add_store_info(ctx)

        ctx.latency_ms = (time.perf_counter() - start) * 1000
        return ctx

    async def _load_business_summary(self) -> dict[str, Any]:
        summaries = await self._summary_repo.find_by_document_id(
            self._tenant.store_id, limit=50,
        )
        if not summaries:
            return {}
        latest = max(summaries, key=lambda s: (s.version_number, s.created_at))
        sections = (latest.metadata or {}).get("sections", {})
        return {
            "summary": latest.summary,
            "version": latest.version_number,
            "sections": sections,
        }

    async def _retrieve_chunks(self, query: str) -> Optional[UnifiedRetrievalResult]:
        filters = RetrievalFilters(
            organization_id=self._tenant.organization_id,
            store_id=self._tenant.store_id,
            knowledge_version=self._tenant.knowledge_version,
            document_status="active",
        )
        return await self._retriever.search(query=query, filters=filters, config=self._conf)

    async def _load_knowledge_version(self) -> Optional[KnowledgeVersionInfo]:
        col = get_knowledge_versions_collection()
        cursor = col.find(
            {"organization_id": self._tenant.organization_id, "store_id": self._tenant.store_id},
        ).sort("version_number", -1).limit(1)
        latest = await cursor.to_list(length=1)
        if latest:
            doc = KnowledgeVersionDocument.from_mongo_dict(latest[0])
            return KnowledgeVersionInfo(
                organization_id=doc.organization_id,
                store_id=doc.store_id,
                version_number=doc.version_number,
                previous_version=doc.previous_version,
                status=doc.status,
                document_count=doc.document_count,
                chunk_count=doc.chunk_count,
                files_processed=doc.files_processed,
                files_skipped=doc.files_skipped,
                total_files=doc.total_files,
                summary_generated=doc.summary_generated,
                embeddings_generated=doc.embeddings_generated,
                vectors_synced=doc.vectors_synced,
                started_at=doc.started_at,
                completed_at=doc.completed_at,
                error=doc.error,
            )
        return None

    async def add_merchant_profile(self, ctx: BuiltContext) -> None:
        ctx.merchant_profile = self._tenant.merchant_id or None

    async def add_store_info(self, ctx: BuiltContext) -> None:
        ctx.store_info = (
            f"Store: {self._tenant.store_slug or self._tenant.store_id} | "
            f"Language: {self._tenant.language} | "
            f"Currency: {self._tenant.currency} | "
            f"Timezone: {self._tenant.timezone}"
        )


def _safe_get(results: tuple, index: int, default: Any = None) -> Any:
    val = results[index] if index < len(results) else None
    if isinstance(val, Exception):
        return default
    return val if val is not None else default
