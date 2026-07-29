import pytest
from unittest.mock import AsyncMock, MagicMock

from app.application.knowledge.retrieval.dto import RetrievedChunkDTO
from app.application.rag.dedup import deduplicate_chunks, _content_fingerprint
from app.application.rag.dto import ChunkReference, Citation, RAGRequest, RAGResponse
from app.application.rag.prompt import build_rag_messages, RAG_SYSTEM_PROMPT
from app.application.rag.service import RagOrchestrationService
from app.application.dto.ai_dto import UsageDTO


# ---------- Dedup tests ----------

class TestContentFingerprint:
    def test_same_text_same_fingerprint(self):
        assert _content_fingerprint("Hello world") == _content_fingerprint("Hello world")

    def test_different_text_different_fingerprint(self):
        assert _content_fingerprint("Hello") != _content_fingerprint("World")

    def test_truncated_to_200_chars(self):
        long = "A" * 500
        assert len(_content_fingerprint(long)) == 32


class TestDeduplicateChunks:
    def make_chunk(self, chunk_id: str, content: str) -> RetrievedChunkDTO:
        return RetrievedChunkDTO(
            chunk_id=chunk_id, document_id="d1", document_title="T",
            chunk_index=0, content=content, score=0.5, rank=1,
        )

    def test_empty_list(self):
        assert deduplicate_chunks([]) == []

    def test_no_duplicates(self):
        chunks = [self.make_chunk("c1", "Hello"), self.make_chunk("c2", "World")]
        result = deduplicate_chunks(chunks)
        assert len(result) == 2

    def test_duplicate_id(self):
        chunks = [self.make_chunk("c1", "Hello"), self.make_chunk("c1", "Hello")]
        result = deduplicate_chunks(chunks)
        assert len(result) == 1

    def test_duplicate_content(self):
        chunks = [self.make_chunk("c1", "Same content"), self.make_chunk("c2", "Same content")]
        result = deduplicate_chunks(chunks)
        assert len(result) == 1

    def test_different_id_same_content(self):
        chunks = [
            self.make_chunk("c1", "Duplicate"),
            self.make_chunk("c2", "Duplicate"),
            self.make_chunk("c3", "Unique"),
        ]
        result = deduplicate_chunks(chunks)
        assert len(result) == 2
        assert result[0].chunk_id == "c1"
        assert result[1].chunk_id == "c3"


# ---------- Prompt tests ----------

class TestBuildRagMessages:
    def test_without_business_summary(self):
        system, user, original = build_rag_messages(
            user_message="What is the price?",
            chunks_context="Chunk content here",
        )
        assert RAG_SYSTEM_PROMPT in system
        assert "Chunk content here" in system
        assert user == "What is the price?"

    def test_with_business_summary(self):
        system, user, original = build_rag_messages(
            user_message="Tell me about policies",
            chunks_context="Policy chunks",
            business_summary_context="Business overview",
            business_summary_version=2,
        )
        assert "Business Context (v2)" in system
        assert "Business overview" in system
        assert "Policy chunks" in system

    def test_with_conversation_history(self):
        system, user, original = build_rag_messages(
            user_message="Follow up",
            chunks_context="Context",
            conversation_history=[{"role": "user", "content": "Previous"}],
        )
        assert "Follow up" in user


class TestChunkReference:
    def test_create(self):
        ref = ChunkReference(
            chunk_id="c1", document_id="d1", document_title="Doc",
            content_snippet="Snip", score=0.9, rank=1,
        )
        assert ref.chunk_id == "c1"


class TestCitation:
    def test_create(self):
        cit = Citation(
            index=1, chunk_id="c1", document_title="Doc",
            content_snippet="Snip", score=0.9, rank=1,
        )
        assert cit.index == 1


class TestRAGRequest:
    def test_minimal(self):
        req = RAGRequest(message="Hello", store_id="store-1")
        assert req.message == "Hello"
        assert req.top_k == 5
        assert req.temperature is None

    def test_full(self):
        req = RAGRequest(
            message="Complex query",
            conversation_id="conv-1",
            store_id="store-1",
            organization_id="org-1",
            customer_id="cust-1",
            model="gpt-4",
            temperature=0.5,
            max_tokens=2048,
            top_k=10,
            score_threshold=0.3,
            use_hybrid=True,
            use_mmr=True,
            rerank=True,
            language="en",
            knowledge_scope="legal",
        )
        assert req.use_hybrid is True
        assert req.rerank is True


# ---------- RagOrchestrationService tests ----------

@pytest.fixture
def mock_retriever():
    r = AsyncMock()
    return r


@pytest.fixture
def mock_chat_service():
    cs = MagicMock()
    cs.chat = AsyncMock()
    return cs


@pytest.fixture
def mock_conversation_service():
    cs = MagicMock()
    cs.get_conversation_history = AsyncMock(return_value=[])
    return cs


@pytest.fixture
def mock_summary_repo():
    r = AsyncMock()
    r.find_by_document_id = AsyncMock(return_value=[])
    return r


@pytest.fixture
def sample_chunks():
    return [
        RetrievedChunkDTO(
            chunk_id="c1", document_id="d1", document_title="Doc 1",
            chunk_index=0, content="The price of product A is $10.",
            score=0.95, rank=1,
        ),
        RetrievedChunkDTO(
            chunk_id="c2", document_id="d2", document_title="Doc 2",
            chunk_index=0, content="Product B costs $20.",
            score=0.85, rank=2,
        ),
    ]


@pytest.fixture
def make_usage():
    return lambda p=10, c=5, t=15: UsageDTO(prompt_tokens=p, completion_tokens=c, total_tokens=t)


@pytest.fixture
def rag_service(mock_retriever, mock_chat_service, mock_conversation_service, mock_summary_repo):
    return RagOrchestrationService(
        retriever_service=mock_retriever,
        chat_service=mock_chat_service,
        conversation_service=mock_conversation_service,
        business_summary_repository=mock_summary_repo,
    )


def _make_chat_response(content: str, usage: UsageDTO, model: str = "gpt-4o-mini", provider: str = "openai"):
    resp = MagicMock()
    resp.message.content = content
    resp.model = model
    resp.provider = provider
    resp.usage = usage
    return resp


class TestRagOrchestrationService:
    @pytest.mark.asyncio
    async def test_answer_basic(self, rag_service, mock_retriever, mock_chat_service, sample_chunks, make_usage):
        mock_retriever.search.return_value = MagicMock(results=sample_chunks, latency_ms=50.0)
        mock_chat_service.chat = AsyncMock(return_value=_make_chat_response(
            "The answer is $10 [citation:1].", make_usage(),
        ))

        request = RAGRequest(message="What is the price of A?", store_id="store-1")
        result = await rag_service.answer(request)

        assert isinstance(result, RAGResponse)
        assert "The answer is $10" in result.response
        assert len(result.citations) == 1
        assert result.citations[0].chunk_id == "c1"
        assert len(result.chunk_references) == 2
        assert 0.0 <= result.confidence_score <= 1.0
        assert result.model == "gpt-4o-mini"
        assert result.provider == "openai"

    @pytest.mark.asyncio
    async def test_answer_no_chunks(self, rag_service, mock_retriever, mock_chat_service, make_usage):
        mock_retriever.search.return_value = MagicMock(results=[], latency_ms=10.0)
        mock_chat_service.chat = AsyncMock(return_value=_make_chat_response("I don't know.", make_usage()))

        result = await rag_service.answer(RAGRequest(message="Unknown", store_id="store-1"))

        assert result.confidence_score == 0.0
        assert len(result.citations) == 0

    @pytest.mark.asyncio
    async def test_answer_with_hybrid_config(self, rag_service, mock_retriever, mock_chat_service, sample_chunks, make_usage):
        mock_retriever.search.return_value = MagicMock(results=sample_chunks, latency_ms=30.0)
        mock_chat_service.chat = AsyncMock(return_value=_make_chat_response("Answer.", make_usage()))

        request = RAGRequest(
            message="Question", store_id="store-1",
            use_hybrid=True, use_mmr=True, rerank=True, top_k=10,
        )
        result = await rag_service.answer(request)

        assert result.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_answer_with_business_summary(self, rag_service, mock_retriever, mock_chat_service, mock_summary_repo, sample_chunks, make_usage):
        mock_retriever.search.return_value = MagicMock(results=sample_chunks, latency_ms=40.0)

        mock_summary = MagicMock()
        mock_summary.version_number = 1
        mock_summary.created_at = None
        mock_summary.summary = "This is a business summary context."
        mock_summary_repo.find_by_document_id = AsyncMock(return_value=[mock_summary])

        mock_chat_service.chat = AsyncMock(return_value=_make_chat_response("Answer based on context.", make_usage()))

        result = await rag_service.answer(RAGRequest(message="Question", store_id="store-1"))

        assert result.business_summary_version == 1
        assert result.confidence_score > 0.0

    @pytest.mark.asyncio
    async def test_answer_with_conversation_history(self, rag_service, mock_retriever, mock_chat_service, mock_conversation_service, sample_chunks, make_usage):
        from app.application.dto.ai_dto import MessageDTO

        mock_retriever.search.return_value = MagicMock(results=sample_chunks, latency_ms=35.0)
        mock_conversation_service.get_conversation_history = AsyncMock(
            return_value=[MessageDTO(role="user", content="Previous question")]
        )

        mock_chat_service.chat = AsyncMock(return_value=_make_chat_response("Follow-up answer.", make_usage()))

        request = RAGRequest(message="Follow up", store_id="store-1", conversation_id="conv-1")
        result = await rag_service.answer(request)

        assert result.conversation_id == "conv-1"

    @pytest.mark.asyncio
    async def test_answer_conversation_service_failure(self, rag_service, mock_retriever, mock_chat_service, mock_conversation_service, sample_chunks, make_usage):
        mock_retriever.search.return_value = MagicMock(results=sample_chunks, latency_ms=30.0)
        mock_conversation_service.get_conversation_history = AsyncMock(side_effect=Exception("DB error"))

        mock_chat_service.chat = AsyncMock(return_value=_make_chat_response("Answer.", make_usage()))

        result = await rag_service.answer(
            RAGRequest(message="Question", store_id="store-1", conversation_id="conv-1")
        )
        assert result.response == "Answer."

    @pytest.mark.asyncio
    async def test_answer_summary_repo_failure(self, rag_service, mock_retriever, mock_chat_service, mock_summary_repo, sample_chunks, make_usage):
        mock_retriever.search.return_value = MagicMock(results=sample_chunks, latency_ms=30.0)
        mock_summary_repo.find_by_document_id = AsyncMock(side_effect=Exception("DB error"))

        mock_chat_service.chat = AsyncMock(return_value=_make_chat_response("Answer without summary.", make_usage()))

        result = await rag_service.answer(RAGRequest(message="Question", store_id="store-1"))
        assert result.business_summary_version is None

    @pytest.mark.asyncio
    async def test_answer_response_text_is_list(self, rag_service, mock_retriever, mock_chat_service, sample_chunks, make_usage):
        mock_retriever.search.return_value = MagicMock(results=sample_chunks, latency_ms=30.0)
        mock_chat_service.chat = AsyncMock(return_value=_make_chat_response(["Hello", "World"], make_usage()))

        result = await rag_service.answer(RAGRequest(message="Hi", store_id="store-1"))
        assert "Hello World" in result.response


class TestExtractCitations:
    def test_extract_single_citation(self, rag_service, sample_chunks):
        text = "According to our docs [citation:1], the price is $10."
        citations = rag_service._extract_citations(text, sample_chunks)

        assert len(citations) == 1
        assert citations[0].index == 1
        assert citations[0].chunk_id == "c1"

    def test_extract_multiple_citations(self, rag_service, sample_chunks):
        text = "First [citation:1] and second [citation:2]."
        citations = rag_service._extract_citations(text, sample_chunks)

        assert len(citations) == 2

    def test_deduplicate_citations(self, rag_service, sample_chunks):
        text = "Ref [citation:1] and again [citation:1]."
        citations = rag_service._extract_citations(text, sample_chunks)

        assert len(citations) == 1

    def test_out_of_range_citation(self, rag_service, sample_chunks):
        text = "Bad ref [citation:99]."
        citations = rag_service._extract_citations(text, sample_chunks)

        assert len(citations) == 0

    def test_no_citations(self, rag_service, sample_chunks):
        text = "Plain text without references."
        citations = rag_service._extract_citations(text, sample_chunks)

        assert citations == []


class TestCalculateConfidence:
    def test_no_chunks(self, rag_service):
        score = rag_service._calculate_confidence([], has_business_summary=False)
        assert score == 0.0

    def test_with_summary_high_score(self, rag_service, sample_chunks):
        score = rag_service._calculate_confidence(sample_chunks, has_business_summary=True)
        assert score > 0.5

    def test_without_summary_low_score(self, rag_service):
        chunks = [
            RetrievedChunkDTO(chunk_id="c1", document_id="d1", document_title="T", chunk_index=0, content="X", score=0.1, rank=1),
        ]
        score = rag_service._calculate_confidence(chunks, has_business_summary=False)
        assert score == pytest.approx(0.2 + 0.8 * 0.1)

    def test_clamped_to_max(self, rag_service):
        chunks = [
            RetrievedChunkDTO(chunk_id="c1", document_id="d1", document_title="T", chunk_index=0, content="X", score=2.0, rank=1),
        ]
        score = rag_service._calculate_confidence(chunks, has_business_summary=True)
        assert score <= 1.0

    def test_clamped_to_min(self, rag_service):
        chunks = [
            RetrievedChunkDTO(chunk_id="c1", document_id="d1", document_title="T", chunk_index=0, content="X", score=-1.0, rank=1),
        ]
        score = rag_service._calculate_confidence(chunks, has_business_summary=False)
        assert score >= 0.0
