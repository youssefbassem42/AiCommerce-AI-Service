from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.application.knowledge.retrieval.dto import RetrievedChunkDTO, UnifiedRetrievalResult
from app.application.knowledge.retrieval.mmr import _cosine_similarity, mmr_rerank
from app.application.knowledge.retrieval.reranker import LLMCrossEncoderReRanker
from app.application.knowledge.retrieval.service import RetrieverService, _keyword_terms
from app.infrastructure.vectorstore.base import SearchResult

# ---------- DTO tests ----------


class TestRetrievalConfig:
    def test_defaults(self):
        cfg = RetrievalConfig()
        assert cfg.top_k == 10
        assert cfg.score_threshold == 0.25
        assert cfg.use_hybrid is False
        assert cfg.use_mmr is False
        assert cfg.mmr_lambda == 0.7
        assert cfg.rerank is False
        assert cfg.rerank_top_k == 5
        assert cfg.embedding_model == "gemini-embedding-001"
        assert cfg.collection_prefix == "kb"

    def test_custom(self):
        cfg = RetrievalConfig(top_k=25, score_threshold=0.5, use_hybrid=True, mmr_lambda=0.5)
        assert cfg.top_k == 25
        assert cfg.score_threshold == 0.5
        assert cfg.use_hybrid is True
        assert cfg.mmr_lambda == 0.5


class TestRetrievalFilters:
    def test_defaults(self):
        f = RetrievalFilters()
        assert f.organization_id is None
        assert f.store_id is None
        assert f.entity_type is None
        assert f.language is None
        assert f.document_type is None
        assert f.knowledge_scope is None
        assert f.business_version is None
        assert f.chunk_ids is None

    def test_full(self):
        f = RetrievalFilters(
            organization_id="org-1",
            store_id="store-1",
            entity_type="product",
            language="en",
            document_type="pdf",
            knowledge_scope="legal",
            business_version=2,
            chunk_ids=["chunk-1", "chunk-2"],
        )
        assert f.organization_id == "org-1"
        assert f.entity_type == "product"


class TestRetrievedChunkDTO:
    def test_minimal(self):
        dto = RetrievedChunkDTO(
            chunk_id="c1",
            document_id="d1",
            document_title="T",
            chunk_index=0,
            content="Hello",
            score=0.9,
            rank=1,
        )
        assert dto.metadata == {}
        assert dto.language is None

    def test_model_dump_roundtrip(self):
        dto = RetrievedChunkDTO(
            chunk_id="c1",
            document_id="d1",
            document_title="T",
            chunk_index=1,
            content="Test",
            score=0.8,
            rank=2,
            metadata={"key": "val"},
        )
        dumped = dto.model_dump()
        assert dumped["chunk_id"] == "c1"
        assert dumped["metadata"] == {"key": "val"}


class TestUnifiedRetrievalResult:
    def test_create(self):
        result = UnifiedRetrievalResult(
            query="test",
            results=[],
            total_count=0,
            strategy="semantic",
            latency_ms=10.0,
            filters_applied={},
        )
        assert result.strategy == "semantic"
        assert result.latency_ms == 10.0


# ---------- MMR unit tests ----------


class TestMMR:
    def test_empty_input(self):
        assert mmr_rerank([], [], [], 5) == []

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError):
            mmr_rerank([0.1, 0.2], [[0.1], [0.2]], [0.5], 5)

    def test_selects_top_without_diversity(self):
        emb = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        scores = [0.9, 0.8, 0.7]
        indices = mmr_rerank([1.0, 0.0], emb, scores, 3, lambda_param=1.0)
        assert indices == [0, 1, 2]

    def test_diversity_low_lambda(self):
        emb = [[1.0, 0.0], [1.0, 0.01], [0.0, 1.0]]
        scores = [0.9, 0.89, 0.5]
        indices = mmr_rerank([1.0, 0.0], emb, scores, 3, lambda_param=0.3)
        assert 2 in indices

    def test_top_k_limit(self):
        emb = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5], [0.3, 0.7]]
        scores = [0.9, 0.8, 0.7, 0.6]
        indices = mmr_rerank([0.5, 0.5], emb, scores, 2, lambda_param=0.5)
        assert len(indices) == 2


class TestCosineSimilarity:
    def test_identical(self):
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal(self):
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_mismatched_length(self):
        assert _cosine_similarity([1.0], [1.0, 0.0]) == 0.0


# ---------- ReRanker tests ----------


class TestLLMCrossEncoderReRanker:
    @pytest.fixture
    def mock_provider(self):
        p = AsyncMock()
        return p

    @pytest.fixture
    def reranker(self, mock_provider):
        return LLMCrossEncoderReRanker(provider=mock_provider, model="gpt-4o-mini")

    @pytest.fixture
    def sample_docs(self):
        return [
            RetrievedChunkDTO(
                chunk_id="c1",
                document_id="d1",
                document_title="T1",
                chunk_index=0,
                content="Doc one content",
                score=0.8,
                rank=1,
            ),
            RetrievedChunkDTO(
                chunk_id="c2",
                document_id="d2",
                document_title="T2",
                chunk_index=1,
                content="Doc two content",
                score=0.6,
                rank=2,
            ),
        ]

    @pytest.mark.asyncio
    async def test_empty_docs(self, reranker):
        result = await reranker.rerank("query", [], 5)
        assert result == []

    @pytest.mark.asyncio
    async def test_single_doc(self, reranker, sample_docs):
        result = await reranker.rerank("query", sample_docs[:1], 5)
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    @pytest.mark.asyncio
    async def test_rerank_with_valid_response(self, reranker, mock_provider, sample_docs):
        mock_response = MagicMock()
        mock_response.message.content = '[{"index": 1, "score": 0.9}, {"index": 0, "score": 0.7}]'
        mock_provider.chat = AsyncMock(return_value=mock_response)

        result = await reranker.rerank("test query", sample_docs, 5)

        assert len(result) == 2
        assert result[0].chunk_id == "c2"
        assert result[0].score == 0.9

    @pytest.mark.asyncio
    async def test_rerank_with_markdown_json(self, reranker, mock_provider, sample_docs):
        mock_response = MagicMock()
        mock_response.message.content = '```json\n[{"index": 0, "score": 0.8}]\n```'
        mock_provider.chat = AsyncMock(return_value=mock_response)

        result = await reranker.rerank("query", sample_docs, 5)
        assert len(result) == 2
        assert result[0].chunk_id == "c1"

    @pytest.mark.asyncio
    async def test_rerank_with_dict_response(self, reranker, mock_provider, sample_docs):
        mock_response = MagicMock()
        mock_response.message.content = '{"scores": [{"index": 1, "score": 0.95}]}'
        mock_provider.chat = AsyncMock(return_value=mock_response)

        result = await reranker.rerank("query", sample_docs, 5)
        assert result[0].chunk_id == "c2"
        assert result[0].score == 0.95

    @pytest.mark.asyncio
    async def test_rerank_invalid_json_fallback(self, reranker, mock_provider, sample_docs):
        mock_response = MagicMock()
        mock_response.message.content = "not valid json"
        mock_provider.chat = AsyncMock(return_value=mock_response)

        result = await reranker.rerank("query", sample_docs, 5)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_rerank_content_truncation(self, reranker, mock_provider):
        long_doc = RetrievedChunkDTO(
            chunk_id="c1",
            document_id="d1",
            document_title="T1",
            chunk_index=0,
            content="A" * 2000,
            score=0.5,
            rank=1,
        )
        short_doc = RetrievedChunkDTO(
            chunk_id="c2",
            document_id="d2",
            document_title="T2",
            chunk_index=1,
            content="Short",
            score=0.4,
            rank=2,
        )
        mock_response = MagicMock()
        mock_response.message.content = '[{"index": 0, "score": 0.9}, {"index": 1, "score": 0.8}]'
        mock_provider.chat = AsyncMock(return_value=mock_response)

        reranker._max_chars_per_doc = 10
        result = await reranker.rerank("query", [long_doc, short_doc], 5)

        assert len(result) == 2


# ---------- RetrieverService tests ----------


@pytest.fixture
def mock_vector_store():
    vs = MagicMock()
    vs.search = AsyncMock()
    vs.collection_exists = AsyncMock(return_value=True)
    return vs


@pytest.fixture
def mock_llm_provider():
    p = AsyncMock()
    p.embeddings = AsyncMock()
    return p


@pytest.fixture
def mock_reranker():
    r = AsyncMock()
    r.rerank = AsyncMock()
    return r


@pytest.fixture
def retriever(mock_vector_store, mock_llm_provider, mock_reranker):
    return RetrieverService(
        vector_store=mock_vector_store,
        llm_provider=mock_llm_provider,
        reranker=mock_reranker,
    )


def make_search_result(chunk_id: str, score: float, rank: int = 0, payload: dict | None = None) -> SearchResult:
    return SearchResult(
        id=chunk_id,
        score=score,
        payload=payload
        or {
            "document_id": "doc-1",
            "document_title": "Test",
            "chunk_index": 0,
            "content": f"Content of {chunk_id}",
        },
    )


class TestRetrieverServiceSemantic:
    @pytest.mark.asyncio
    async def test_semantic_search(self, retriever, mock_vector_store, mock_llm_provider):
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1, 0.2, 0.3]])
        mock_vector_store.search.return_value = [
            make_search_result(
                "c1",
                0.9,
                payload={
                    "document_id": "d1",
                    "document_title": "Doc 1",
                    "chunk_index": 0,
                    "content": "Hello world",
                    "language": "en",
                },
            ),
            make_search_result(
                "c2",
                0.8,
                payload={
                    "document_id": "d1",
                    "document_title": "Doc 1",
                    "chunk_index": 1,
                    "content": "More text",
                    "language": "en",
                },
            ),
        ]

        result = await retriever.search(query="test", config=RetrievalConfig(top_k=5))

        assert isinstance(result, UnifiedRetrievalResult)
        assert len(result.results) == 2
        assert result.strategy == "semantic"
        assert result.total_count == 2
        assert result.results[0].chunk_id == "c1"
        assert result.results[0].score == 0.9

    @pytest.mark.asyncio
    async def test_empty_collection(self, retriever, mock_vector_store, mock_llm_provider):
        mock_vector_store.collection_exists = AsyncMock(return_value=False)
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1, 0.2]])

        result = await retriever.search(query="test")

        assert len(result.results) == 0
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_embedding_failure(self, retriever, mock_llm_provider):
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[])

        with pytest.raises(RuntimeError, match="Embedding returned empty result"):
            await retriever.search(query="test")


class TestRetrieverServiceFilters:
    @pytest.mark.asyncio
    async def test_build_filter_conditions_all(self, retriever, mock_vector_store, mock_llm_provider):
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1]])
        mock_vector_store.search.return_value = []

        filters = RetrievalFilters(
            organization_id="org-1",
            store_id="store-1",
            entity_type="product",
            language="en",
            document_type="pdf",
            knowledge_scope="legal",
            business_version=2,
            chunk_ids=["c1", "c2"],
        )
        result = await retriever.search(query="test", filters=filters)

        assert result.filters_applied["organization_id"] == "org-1"
        assert result.filters_applied["store_id"] == "store-1"
        must = mock_vector_store.search.call_args.kwargs["must"]
        assert {"key": "entity_type", "op": "eq", "value": "product"} in must

    @pytest.mark.asyncio
    async def test_build_filter_conditions_entity_type_omitted_when_not_set(
        self, retriever, mock_vector_store, mock_llm_provider
    ):
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1]])
        mock_vector_store.search.return_value = []

        await retriever.search(query="test", filters=RetrievalFilters(store_id="store-1"))

        must = mock_vector_store.search.call_args.kwargs["must"]
        assert all(c.get("key") != "entity_type" for c in must)


class TestRetrieverServiceHybrid:
    @pytest.mark.asyncio
    async def test_hybrid_search_calls_rrf(self, retriever, mock_vector_store, mock_llm_provider):
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1, 0.2]])
        mock_vector_store.search.return_value = [
            make_search_result("c1", 0.9),
            make_search_result("c2", 0.8),
        ]

        with patch.object(
            retriever,
            "_keyword_search",
            AsyncMock(
                return_value=[
                    RetrievedChunkDTO(
                        chunk_id="c3",
                        document_id="d1",
                        document_title="T",
                        chunk_index=2,
                        content="KW result",
                        score=1.0,
                        rank=1,
                    ),
                ]
            ),
        ):
            result = await retriever.search(query="test", config=RetrievalConfig(top_k=5, use_hybrid=True))

            assert len(result.results) >= 1
            assert result.strategy == "hybrid"

    @pytest.mark.asyncio
    async def test_hybrid_semantic_search_uses_config_score_threshold(self, retriever, mock_vector_store, mock_llm_provider):
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1, 0.2]])
        mock_vector_store.search.return_value = [make_search_result("c1", 0.9)]

        with patch.object(retriever, "_keyword_search", AsyncMock(return_value=[])):
            await retriever.search(
                query="test",
                config=RetrievalConfig(top_k=5, use_hybrid=True, score_threshold=0.42),
            )

        search_kwargs = mock_vector_store.search.await_args.kwargs
        assert search_kwargs["score_threshold"] == 0.42

    @pytest.mark.asyncio
    async def test_hybrid_semantic_search_never_uses_zero_threshold_when_configured(
        self, retriever, mock_vector_store, mock_llm_provider
    ):
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1, 0.2]])
        mock_vector_store.search.return_value = [make_search_result("c1", 0.9)]

        with patch.object(retriever, "_keyword_search", AsyncMock(return_value=[])):
            await retriever.search(query="test", config=RetrievalConfig(top_k=5, use_hybrid=True))

        search_kwargs = mock_vector_store.search.await_args.kwargs
        assert search_kwargs["score_threshold"] == 0.25


class TestKeywordTerms:
    def test_drops_stopwords(self):
        assert _keyword_terms("What is your return policy?") == ["return", "policy"]

    def test_keeps_product_terms(self):
        assert _keyword_terms("I want a laptop with 16GB RAM") == ["laptop", "16gb", "ram"]

    def test_empty_query(self):
        assert _keyword_terms("what is the") == []

    def test_caps_term_count(self):
        assert len(_keyword_terms("one two three four five six seven eight nine ten")) == 8


class TestRetrieverServiceMMR:
    @pytest.mark.asyncio
    async def test_mmr_search(self, retriever, mock_vector_store, mock_llm_provider):
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1, 0.2]])
        mock_vector_store.search.return_value = [
            make_search_result(
                "c1",
                0.9,
                payload={
                    "document_id": "d1",
                    "document_title": "T",
                    "chunk_index": 0,
                    "content": "A",
                    "_embedding": [0.1, 0.2],
                },
            ),
            make_search_result(
                "c2",
                0.8,
                payload={
                    "document_id": "d1",
                    "document_title": "T",
                    "chunk_index": 1,
                    "content": "B",
                    "_embedding": [0.3, 0.4],
                },
            ),
            make_search_result(
                "c3",
                0.7,
                payload={
                    "document_id": "d1",
                    "document_title": "T",
                    "chunk_index": 2,
                    "content": "C",
                    "_embedding": [0.5, 0.6],
                },
            ),
        ]

        result = await retriever.search(query="test", config=RetrievalConfig(top_k=3, use_mmr=True))

        assert result.strategy == "mmr"


class TestRetrieverServiceRerank:
    @pytest.mark.asyncio
    async def test_rerank_called(self, retriever, mock_vector_store, mock_llm_provider, mock_reranker):
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1, 0.2]])
        mock_vector_store.search.return_value = [
            make_search_result("c1", 0.9),
            make_search_result("c2", 0.8),
        ]

        reranked = [
            RetrievedChunkDTO(
                chunk_id="c2", document_id="d1", document_title="T", chunk_index=1, content="B", score=0.95, rank=1
            ),
            RetrievedChunkDTO(
                chunk_id="c1", document_id="d1", document_title="T", chunk_index=0, content="A", score=0.85, rank=2
            ),
        ]
        mock_reranker.rerank = AsyncMock(return_value=reranked)

        result = await retriever.search(query="test", config=RetrievalConfig(top_k=5, rerank=True))

        assert result.strategy == "reranked"
        mock_reranker.rerank.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rerank_skipped_when_no_reranker(self, mock_vector_store, mock_llm_provider):
        svc = RetrieverService(vector_store=mock_vector_store, llm_provider=mock_llm_provider)
        mock_llm_provider.embeddings.return_value = MagicMock(embeddings=[[0.1]])
        mock_vector_store.search.return_value = [make_search_result("c1", 0.9)]

        result = await svc.search(query="test", config=RetrievalConfig(top_k=5, rerank=True))
        assert result.strategy == "semantic"


class TestRetrieverServiceSearchByEmbedding:
    @pytest.mark.asyncio
    async def test_search_by_embedding(self, retriever, mock_vector_store):
        mock_vector_store.search.return_value = [make_search_result("c1", 0.9)]

        result = await retriever.search_by_embedding(
            embedding=[0.1, 0.2],
            query_text="test",
            config=RetrievalConfig(top_k=5),
        )

        assert len(result.results) == 1
        assert result.strategy == "embedding"

    @pytest.mark.asyncio
    async def test_search_by_embedding_no_collection(self, retriever, mock_vector_store):
        mock_vector_store.collection_exists = AsyncMock(return_value=False)

        result = await retriever.search_by_embedding(embedding=[0.1])

        assert len(result.results) == 0
