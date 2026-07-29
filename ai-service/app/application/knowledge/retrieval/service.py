import logging
import time
import math
from typing import Any, Optional

from qdrant_client.http import models as qdrant_models

from app.application.dto.ai_dto import EmbeddingRequest
from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.application.knowledge.retrieval.dto import RetrievedChunkDTO, UnifiedRetrievalResult
from app.application.knowledge.retrieval.mmr import mmr_rerank
from app.application.knowledge.retrieval.reranker import ReRanker
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.vectorstore.base import SearchResult, VectorStore

logger = logging.getLogger(__name__)


class RetrieverService:
    def __init__(
        self,
        vector_store: VectorStore,
        llm_provider: BaseLLMProvider,
        reranker: Optional[ReRanker] = None,
        default_config: Optional[RetrievalConfig] = None,
        tenant: Optional["TenantContext"] = None,
    ):
        self._vector_store = vector_store
        self._llm_provider = llm_provider
        self._reranker = reranker
        self._default_config = default_config or RetrievalConfig()
        self._tenant = tenant
        self._collection_cache: dict[str, bool] = {}

    async def search(
        self,
        query: str,
        filters: Optional[RetrievalFilters] = None,
        config: Optional[RetrievalConfig] = None,
    ) -> UnifiedRetrievalResult:
        cfg = config or self._default_config
        filters = self._enforce_tenant_scope(filters or RetrievalFilters())
        start = time.perf_counter()

        query_embedding = await self._embed_query(query, cfg.embedding_model)
        must = self._build_filter_conditions(filters)
        collection_name = self._collection_name(filters, cfg)

        if not await self._ensure_collection(collection_name):
            return UnifiedRetrievalResult(
                query=query,
                results=[],
                total_count=0,
                strategy=cfg.embedding_model,
                latency_ms=(time.perf_counter() - start) * 1000,
                filters_applied=filters.model_dump(exclude_none=True),
            )

        strategy = "semantic"
        results: list[RetrievedChunkDTO] = []

        if cfg.use_hybrid:
            strategy = "hybrid"
            results = await self._hybrid_search(
                collection_name=collection_name,
                query_embedding=query_embedding,
                query_text=query,
                cfg=cfg,
                must=must,
            )
        else:
            results = await self._semantic_search(
                collection_name=collection_name,
                query_embedding=query_embedding,
                cfg=cfg,
                must=must,
            )

        if cfg.use_mmr and len(results) > 1:
            strategy = "mmr"
            results = await self._apply_mmr(query_embedding, results, cfg)

        if cfg.rerank and self._reranker is not None and results:
            strategy = "reranked"
            results = await self._reranker.rerank(query, results, cfg.rerank_top_k)

        latency = (time.perf_counter() - start) * 1000

        return UnifiedRetrievalResult(
            query=query,
            results=results[:cfg.top_k],
            total_count=len(results),
            strategy=strategy,
            latency_ms=latency,
            filters_applied=filters.model_dump(exclude_none=True),
        )

    async def search_by_embedding(
        self,
        embedding: list[float],
        filters: Optional[RetrievalFilters] = None,
        config: Optional[RetrievalConfig] = None,
        query_text: str = "",
    ) -> UnifiedRetrievalResult:
        cfg = config or self._default_config
        filters = self._enforce_tenant_scope(filters or RetrievalFilters())
        start = time.perf_counter()

        must = self._build_filter_conditions(filters)
        collection_name = self._collection_name(filters, cfg)

        if not await self._ensure_collection(collection_name):
            return UnifiedRetrievalResult(
                query=query_text,
                results=[],
                total_count=0,
                strategy="embedding",
                latency_ms=(time.perf_counter() - start) * 1000,
                filters_applied=filters.model_dump(exclude_none=True),
            )

        results = await self._semantic_search(
            collection_name=collection_name,
            query_embedding=embedding,
            cfg=cfg,
            must=must,
        )

        if cfg.use_mmr and len(results) > 1:
            results = await self._apply_mmr(embedding, results, cfg)

        latency = (time.perf_counter() - start) * 1000

        return UnifiedRetrievalResult(
            query=query_text,
            results=results[:cfg.top_k],
            total_count=len(results),
            strategy="embedding",
            latency_ms=latency,
            filters_applied=filters.model_dump(exclude_none=True),
        )

    async def _semantic_search(
        self,
        collection_name: str,
        query_embedding: list[float],
        cfg: RetrievalConfig,
        must: Optional[list[dict[str, Any]]] = None,
    ) -> list[RetrievedChunkDTO]:
        raw = await self._vector_store.search(
            collection_name=collection_name,
            vector=query_embedding,
            limit=cfg.top_k * 2,
            must=must,
            score_threshold=cfg.score_threshold if cfg.score_threshold > 0 else None,
        )
        return self._to_dtos(raw)

    async def _hybrid_search(
        self,
        collection_name: str,
        query_embedding: list[float],
        query_text: str,
        cfg: RetrievalConfig,
        must: Optional[list[dict[str, Any]]] = None,
    ) -> list[RetrievedChunkDTO]:
        limit = cfg.top_k * 2

        semantic_raw = await self._vector_store.search(
            collection_name=collection_name,
            vector=query_embedding,
            limit=limit,
            must=must,
            score_threshold=0.0,
        )
        semantic_dtos = self._to_dtos(semantic_raw)
        for dto in semantic_dtos:
            dto.metadata["_semantic_rank"] = dto.rank

        keyword_dtos = await self._keyword_search(
            collection_name=collection_name,
            query_text=query_text,
            limit=limit,
            must=must,
        )

        fused = self._reciprocal_rank_fusion(semantic_dtos, keyword_dtos, cfg.top_k)
        self._reindex_ranks(fused)
        return fused

    async def _keyword_search(
        self,
        collection_name: str,
        query_text: str,
        limit: int,
        must: Optional[list[dict[str, Any]]] = None,
    ) -> list[RetrievedChunkDTO]:
        from app.infrastructure.qdrant.provider import QdrantProvider

        if not isinstance(self._vector_store, QdrantProvider):
            logger.warning("Keyword search requires QdrantProvider, falling back to semantic")
            return []

        client = self._vector_store._client
        if client is None:
            return []

        scroll_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="content",
                    match=qdrant_models.MatchText(text=query_text),
                ),
            ],
        )
        if must:
            from app.infrastructure.qdrant.provider import _build_filter
            parsed = _build_filter(must=must)
            if parsed and parsed.must:
                scroll_filter.must.extend(parsed.must)

        try:
            points, _ = client.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            logger.warning("Qdrant scroll/full-text search failed", exc_info=True)
            return []

        results = []
        for pt in points:
            results.append(SearchResult(
                id=str(pt.id),
                score=1.0,
                payload=pt.payload or {},
            ))
        return self._to_dtos(results)

    def _reciprocal_rank_fusion(
        self,
        semantic: list[RetrievedChunkDTO],
        keyword: list[RetrievedChunkDTO],
        top_k: int,
        k: int = 60,
    ) -> list[RetrievedChunkDTO]:
        score_map: dict[str, float] = {}
        seen: dict[str, RetrievedChunkDTO] = {}

        for rank, dto in enumerate(semantic):
            rrf_score = 1.0 / (k + rank + 1)
            score_map[dto.chunk_id] = score_map.get(dto.chunk_id, 0.0) + rrf_score
            seen[dto.chunk_id] = dto

        for rank, dto in enumerate(keyword):
            rrf_score = 1.0 / (k + rank + 1)
            score_map[dto.chunk_id] = score_map.get(dto.chunk_id, 0.0) + rrf_score
            if dto.chunk_id not in seen:
                seen[dto.chunk_id] = dto

        sorted_ids = sorted(score_map, key=score_map.get, reverse=True)
        fused = [seen[cid] for cid in sorted_ids[:top_k]]
        for i, dto in enumerate(fused):
            dto.score = score_map[dto.chunk_id]
        return fused

    async def _apply_mmr(
        self,
        query_embedding: list[float],
        results: list[RetrievedChunkDTO],
        cfg: RetrievalConfig,
    ) -> list[RetrievedChunkDTO]:
        candidate_embeddings = [
            dto.metadata.get("_embedding", query_embedding)
            for dto in results
        ]
        candidate_scores = [dto.score for dto in results]

        indices = mmr_rerank(
            query_embedding=query_embedding,
            candidate_embeddings=candidate_embeddings,
            candidate_scores=candidate_scores,
            top_k=cfg.top_k,
            lambda_param=cfg.mmr_lambda,
        )

        selected = [results[i] for i in indices]
        self._reindex_ranks(selected)
        return selected

    async def _embed_query(self, query: str, model: str) -> list[float]:
        request = EmbeddingRequest(input=query, model=model)
        response = await self._llm_provider.embeddings(request)
        if not response.embeddings:
            raise RuntimeError(f"Embedding returned empty result for model '{model}'")
        return response.embeddings[0]

    def _enforce_tenant_scope(self, filters: RetrievalFilters) -> RetrievalFilters:
        if self._tenant:
            if not filters.organization_id:
                filters.organization_id = self._tenant.organization_id
            if not filters.store_id:
                filters.store_id = self._tenant.store_id
            if not filters.knowledge_version:
                filters.knowledge_version = self._tenant.knowledge_version
        if filters.organization_id is None or filters.store_id is None:
            logger.warning(
                "No tenant scope set — retrieval would be global. "
                "Always provide organization_id and store_id via tenant or filters."
            )
        return filters

    def _build_filter_conditions(
        self,
        filters: RetrievalFilters,
    ) -> Optional[list[dict[str, Any]]]:
        conditions: list[dict[str, Any]] = []

        if filters.organization_id:
            conditions.append({"key": "organization_id", "op": "eq", "value": filters.organization_id})
        if filters.store_id:
            conditions.append({"key": "store_id", "op": "eq", "value": filters.store_id})
        if filters.language:
            conditions.append({"key": "language", "op": "eq", "value": filters.language})
        if filters.document_type:
            conditions.append({"key": "document_type", "op": "eq", "value": filters.document_type})
        if filters.document_status:
            conditions.append({"key": "document_status", "op": "eq", "value": filters.document_status})
        else:
            conditions.append({"key": "document_status", "op": "eq", "value": "active"})
        if filters.knowledge_scope:
            conditions.append({"key": "knowledge_scope", "op": "eq", "value": filters.knowledge_scope})
        if filters.knowledge_version is not None:
            conditions.append({"key": "knowledge_version", "op": "eq", "value": filters.knowledge_version})
        if filters.business_version is not None:
            conditions.append({"key": "business_version", "op": "eq", "value": filters.business_version})
        if filters.chunk_ids:
            conditions.append({"key": "chunk_id", "op": "has_id", "value": filters.chunk_ids})

        return conditions if conditions else None

    def _collection_name(self, filters: RetrievalFilters, cfg: RetrievalConfig) -> str:
        if self._tenant:
            return self._tenant.collection_name
        tenant = filters.store_id or filters.organization_id or "default"
        return f"{cfg.collection_prefix}_{tenant}"

    async def _ensure_collection(self, name: str) -> bool:
        if name in self._collection_cache:
            return True
        exists = await self._vector_store.collection_exists(name)
        if exists:
            self._collection_cache[name] = True
        return exists

    def _to_dtos(self, results: list[SearchResult]) -> list[RetrievedChunkDTO]:
        dtos = []
        for i, r in enumerate(results):
            payload = r.payload or {}
            dtos.append(RetrievedChunkDTO(
                chunk_id=r.id,
                document_id=payload.get("document_id", ""),
                document_title=payload.get("document_title", ""),
                chunk_index=payload.get("chunk_index", 0),
                content=payload.get("content", ""),
                score=r.score,
                rank=i + 1,
                metadata=payload,
                language=payload.get("language"),
                source_type=payload.get("source_type"),
            ))
        return dtos

    @staticmethod
    def _reindex_ranks(dtos: list[RetrievedChunkDTO]) -> None:
        for i, dto in enumerate(dtos):
            dto.rank = i + 1
