from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO
from app.application.rag.dto import RAGRequest, RAGResponse
from app.application.rag.service import ESCALATION_CONFIDENCE_THRESHOLD, RagOrchestrationService


@pytest.fixture
def retriever():
    r = AsyncMock()
    r.search.return_value = MagicMock(results=[], total_count=0)
    return r


@pytest.fixture
def chat_service():
    c = AsyncMock()
    c.chat.return_value = ChatResponse(
        id="test", model="gpt-4o-mini", provider="openai",
        message=MessageDTO(role="assistant", content="Test response"),
        usage=UsageDTO(), latency_ms=0,
    )
    return c


@pytest.fixture
def rag_service(retriever, chat_service):
    return RagOrchestrationService(
        retriever_service=retriever,
        chat_service=chat_service,
    )


class TestRAGServiceEdgeCases:
    async def test_no_chunks_retrieved(self, rag_service, retriever):
        retriever.search.return_value = MagicMock(results=[], total_count=0)
        result = await rag_service.answer(RAGRequest(message="test query", store_id="s1"))
        assert result.confidence_score == 0.0
        assert result.response is not None

    async def test_llm_unavailable(self, rag_service, chat_service):
        from app.core.ai_exceptions import ProviderUnavailableException
        chat_service.chat.side_effect = ProviderUnavailableException("openai", "LLM unavailable")
        result = await rag_service.answer(RAGRequest(message="test query", store_id="s1"))
        assert "unable to generate" in result.response.lower() or "found" in result.response.lower()
        assert result.provider == "fallback"

    async def test_confidence_with_no_chunks(self, rag_service):
        assert rag_service._calculate_confidence([], has_business_summary=False) == 0.0
        assert rag_service._calculate_confidence([], has_business_summary=True) == 0.0

    async def test_confidence_with_business_summary(self, rag_service):
        mock_chunk = MagicMock(score=0.8)
        result = rag_service._calculate_confidence([mock_chunk], has_business_summary=True)
        assert 0.3 <= result <= 1.0

    async def test_confidence_without_business_summary(self, rag_service):
        mock_chunk = MagicMock(score=0.8)
        result = rag_service._calculate_confidence([mock_chunk], has_business_summary=False)
        assert 0.2 <= result <= 1.0

    async def test_confidence_scores_above_1_clamped(self, rag_service):
        mock_chunk = MagicMock(score=2.0)
        result = rag_service._calculate_confidence([mock_chunk], has_business_summary=True)
        assert result == 1.0

    async def test_citation_extraction_empty_text(self, rag_service):
        citations = rag_service._extract_citations("no citations here", [])
        assert citations == []

    async def test_citation_extraction_with_matches(self, rag_service):
        chunks = [MagicMock(chunk_id="c1", document_title="Doc1", content="content here", score=0.9, rank=1)]
        citations = rag_service._extract_citations("See [citation: 1] for details", chunks)
        assert len(citations) == 1
        assert citations[0].chunk_id == "c1"

    async def test_citation_out_of_range(self, rag_service):
        chunks = [MagicMock(chunk_id="c1", document_title="Doc1", content="content", score=0.9, rank=1)]
        citations = rag_service._extract_citations("See [citation: 99]", chunks)
        assert citations == []

    async def test_citation_duplicates_skipped(self, rag_service):
        chunks = [MagicMock(chunk_id="c1", document_title="Doc1", content="content", score=0.9, rank=1)]
        citations = rag_service._extract_citations("[citation: 1] and [citation: 1]", chunks)
        assert len(citations) == 1

    async def test_no_escalation_when_ticket_service_not_injected(self, rag_service, retriever, chat_service):
        retriever.search.return_value = MagicMock(results=[], total_count=0)
        chat_service.chat.return_value = ChatResponse(
            id="test", model="gpt-4o-mini", provider="openai",
            message=MessageDTO(role="assistant", content="response"),
            usage=UsageDTO(), latency_ms=0,
        )
        result = await rag_service.answer(RAGRequest(
            message="test", store_id="s1", customer_id="c1",
        ))
        assert result is not None

    async def test_escalation_skipped_when_confidence_high(self, rag_service, retriever, chat_service):
        ticket_service = AsyncMock()
        rag_service._ticket_service = ticket_service
        rag_service._conversation_service = AsyncMock()
        rag_service._conversation_service.get_conversation_history = AsyncMock(return_value=[])

        mock_chunk = MagicMock(content="some content", chunk_id="c1", rank=1, score=0.95, document_id="doc1", document_title="Doc1")
        retriever.search = AsyncMock(return_value=MagicMock(results=[mock_chunk], total_count=1))
        chat_service.chat.return_value = ChatResponse(
            id="test", model="gpt-4o-mini", provider="openai",
            message=MessageDTO(role="assistant", content="Great response"),
            usage=UsageDTO(), latency_ms=0,
        )

        result = await rag_service.answer(RAGRequest(
            message="test", store_id="s1", customer_id="c1",
        ))
        assert result.confidence_score >= ESCALATION_CONFIDENCE_THRESHOLD
        ticket_service.create_ticket.assert_not_called()

    async def test_escalation_triggers_on_low_confidence(self, rag_service, retriever, chat_service):
        ticket_service = AsyncMock()
        ticket_service.create_ticket = AsyncMock()
        rag_service._ticket_service = ticket_service
        conv_service = AsyncMock()
        conv_service.get_conversation_history = AsyncMock(return_value=[])
        rag_service._conversation_service = conv_service

        retriever.search.return_value = MagicMock(results=[], total_count=0)
        chat_service.chat.return_value = ChatResponse(
            id="test", model="gpt-4o-mini", provider="openai",
            message=MessageDTO(role="assistant", content="not confident"),
            usage=UsageDTO(), latency_ms=0,
        )

        result = await rag_service.answer(RAGRequest(
            message="help", store_id="s1", customer_id="c1",
        ))
        assert result.confidence_score < ESCALATION_CONFIDENCE_THRESHOLD
        ticket_service.create_ticket.assert_called_once()

    async def test_escalation_skipped_without_customer_id(self, rag_service, retriever, chat_service):
        ticket_service = AsyncMock()
        rag_service._ticket_service = ticket_service

        result = await rag_service.answer(RAGRequest(
            message="help", store_id="s1",
        ))
        ticket_service.create_ticket.assert_not_called()

    async def test_escalation_failure_does_not_break_main_flow(self, rag_service, retriever, chat_service):
        ticket_service = AsyncMock()
        ticket_service.create_ticket.side_effect = Exception("Ticket creation failed")
        conv_service = AsyncMock()
        conv_service.get_conversation_history = AsyncMock(return_value=[])
        rag_service._ticket_service = ticket_service
        rag_service._conversation_service = conv_service

        result = await rag_service.answer(RAGRequest(
            message="help", store_id="s1", customer_id="c1",
        ))
        assert result is not None
        assert result.response is not None
