from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.dto.ai_dto import ChatRequest as AIChatRequest
from app.application.dto.ai_dto import MessageDTO, UsageDTO
from app.application.knowledge.retrieval import RetrieverService
from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.application.rag.dedup import deduplicate_chunks
from app.application.rag.dto import ChunkReference, Citation, RAGRequest, RAGResponse, RAGStreamingChunk
from app.application.rag.prompt import build_rag_messages
from app.application.services.chat_service import ChatService
from app.application.services.conversation_service import ConversationService
from app.application.ticket.dto.ticket_dto import TicketCreateDTO
from app.application.ticket.services.ticket_service import TicketService
from app.core.ai_exceptions import ProviderUnavailableException, RateLimitException
from app.core.ai_settings import ai_settings
from app.domain.knowledge.repositories.business_summary_repository import BusinessSummaryRepository

if TYPE_CHECKING:
    from app.agents.support.agent import SupportAgent

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 2000
MAX_CHUNKS_IN_CONTEXT = 10

ESCALATION_CONFIDENCE_THRESHOLD = 0.3


@dataclass
class RAGContext:
    chunks: list
    chunk_refs: list[ChunkReference]
    business_summary_text: str | None
    business_summary_version: int | None
    chunks_context: str
    system_content: str
    user_content: str
    model: str
    ai_request: AIChatRequest


class RagOrchestrationService:
    def __init__(
        self,
        retriever_service: RetrieverService,
        chat_service: ChatService,
        conversation_service: ConversationService | None = None,
        business_summary_repository: BusinessSummaryRepository | None = None,
        ticket_service: TicketService | None = None,
        support_agent: SupportAgent | None = None,
    ):
        self._retriever = retriever_service
        self._chat = chat_service
        self._conversation_service = conversation_service
        self._summary_repo = business_summary_repository
        self._ticket_service = ticket_service
        self._support_agent = support_agent

    async def _prepare_context(self, request: RAGRequest) -> RAGContext:
        model = request.model or ai_settings.DEFAULT_MODEL

        retrieval_config = RetrievalConfig(
            top_k=min(request.top_k, MAX_CHUNKS_IN_CONTEXT),
            score_threshold=request.score_threshold,
            use_hybrid=request.use_hybrid,
            use_mmr=request.use_mmr,
            rerank=request.rerank,
        )

        retrieval_filters = RetrievalFilters(
            organization_id=request.organization_id,
            store_id=request.store_id,
            language=request.language,
            knowledge_scope=request.knowledge_scope,
        )

        retrieval_result = await self._retriever.search(
            query=request.message,
            filters=retrieval_filters,
            config=retrieval_config,
        )

        chunks = deduplicate_chunks(retrieval_result.results)
        chunk_refs = [
            ChunkReference(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                content_snippet=c.content[:200],
                score=c.score,
                rank=c.rank,
            )
            for c in chunks
        ]

        business_summary_text = None
        business_summary_version = None

        if self._summary_repo:
            try:
                summaries = await self._summary_repo.find_by_document_id(
                    document_id=request.store_id,
                )
                if summaries:
                    latest = max(summaries, key=lambda s: (s.version_number, s.created_at))
                    business_summary_text = latest.summary
                    business_summary_version = latest.version_number
            except Exception:
                logger.warning("Failed to load business summary for store '%s'", request.store_id, exc_info=True)

        chunks_context_lines = []
        for i, c in enumerate(chunks[:MAX_CHUNKS_IN_CONTEXT]):
            snippet = c.content[:MAX_CHUNK_CHARS]
            chunks_context_lines.append(
                f"\n### Retrieved Knowledge Chunk [{i + 1}]\n**Source:** {c.document_title}\n{snippet}\n"
            )

        chunks_context = "\n".join(chunks_context_lines)

        system_content, user_content, _ = build_rag_messages(
            user_message=request.message,
            chunks_context=chunks_context,
            business_summary_context=business_summary_text,
            business_summary_version=business_summary_version,
        )

        messages = [MessageDTO(role="system", content=system_content)]

        if request.conversation_id and self._conversation_service:
            try:
                history = await self._conversation_service.get_conversation_history(
                    request.conversation_id,
                    store_id=request.store_id,
                )
                if history:
                    messages.extend(history)
            except Exception:
                logger.warning("Failed to load conversation history for '%s'", request.conversation_id)

        messages.append(MessageDTO(role="user", content=user_content))

        ai_request = AIChatRequest(
            messages=messages,
            model=model,
            temperature=request.temperature or 0.3,
            max_tokens=request.max_tokens or 1024,
        )

        return RAGContext(
            chunks=chunks,
            chunk_refs=chunk_refs,
            business_summary_text=business_summary_text,
            business_summary_version=business_summary_version,
            chunks_context=chunks_context,
            system_content=system_content,
            user_content=user_content,
            model=model,
            ai_request=ai_request,
        )

    async def answer(self, request: RAGRequest) -> RAGResponse:
        start = time.perf_counter()

        ctx = await self._prepare_context(request)

        chat_latency_start = time.perf_counter()
        try:
            llm_response = await self._chat.chat(
                request=ctx.ai_request,
                conversation_id=request.conversation_id,
                store_id=request.store_id,
            )
            (time.perf_counter() - chat_latency_start) * 1000
            llm_success = True
        except (RateLimitException, ProviderUnavailableException) as e:
            (time.perf_counter() - chat_latency_start) * 1000
            logger.warning("LLM unavailable (%s). Returning retrieved context directly.", e)
            llm_success = False

        if llm_success:
            response_text = llm_response.message.content
            if isinstance(response_text, list):
                response_text = " ".join(str(item) for item in response_text)

            citations = self._extract_citations(response_text, ctx.chunks[:MAX_CHUNKS_IN_CONTEXT])
            confidence = self._calculate_confidence(ctx.chunks, ctx.business_summary_text is not None)
            result_provider = llm_response.provider
            result_usage = llm_response.usage
        else:
            products = "\n".join(f"- {c.document_title}: {c.content[:200]}" for c in ctx.chunks[:MAX_CHUNKS_IN_CONTEXT])
            response_text = (
                "I found the following relevant products from your catalog:\n\n"
                f"{products}\n\n"
                "I'm currently unable to generate a detailed recommendation because "
                "the AI language model is temporarily unavailable (rate limit reached). "
                "Please try again later."
            )
            citations = [
                Citation(
                    index=i + 1,
                    chunk_id=c.chunk_id,
                    document_title=c.document_title,
                    content_snippet=c.content[:200],
                    score=c.score,
                    rank=c.rank,
                )
                for i, c in enumerate(ctx.chunks[:MAX_CHUNKS_IN_CONTEXT])
            ]
            confidence = self._calculate_confidence(ctx.chunks, ctx.business_summary_text is not None)
            result_usage = UsageDTO()

        total_latency = (time.perf_counter() - start) * 1000

        response = RAGResponse(
            response=response_text,
            citations=citations,
            chunk_references=ctx.chunk_refs,
            confidence_score=confidence,
            latency_ms=total_latency,
            model=ctx.model,
            provider=result_provider if llm_success else "fallback",
            usage=result_usage,
            business_summary_version=ctx.business_summary_version,
            conversation_id=request.conversation_id,
        )

        await self._check_escalation(request, response)

        return response

    async def answer_stream(self, request: RAGRequest) -> AsyncGenerator[RAGStreamingChunk, None]:
        start = time.perf_counter()

        ctx = await self._prepare_context(request)

        try:
            accumulated = []
            stream_provider = None
            async for chunk in self._chat.stream(
                request=ctx.ai_request,
                conversation_id=request.conversation_id,
            ):
                if chunk.content:
                    accumulated.append(chunk.content)
                if stream_provider is None and chunk.provider:
                    stream_provider = chunk.provider
                yield RAGStreamingChunk(
                    type="content",
                    content=chunk.content,
                    finish_reason=chunk.finish_reason,
                )

            response_text = "".join(accumulated)
            citations = self._extract_citations(response_text, ctx.chunks[:MAX_CHUNKS_IN_CONTEXT])
            confidence = self._calculate_confidence(ctx.chunks, ctx.business_summary_text is not None)
            total_latency = (time.perf_counter() - start) * 1000

            yield RAGStreamingChunk(
                type="metadata",
                citations=citations,
                chunk_references=ctx.chunk_refs,
                confidence_score=confidence,
                latency_ms=total_latency,
                model=ctx.model,
                provider=stream_provider or ctx.model,
                business_summary_version=ctx.business_summary_version,
                conversation_id=request.conversation_id,
            )

        except (RateLimitException, ProviderUnavailableException) as e:
            logger.warning("LLM unavailable during stream (%s). Returning retrieved context directly.", e)

            products = "\n".join(f"- {c.document_title}: {c.content[:200]}" for c in ctx.chunks[:MAX_CHUNKS_IN_CONTEXT])
            response_text = (
                "I found the following relevant products from your catalog:\n\n"
                f"{products}\n\n"
                "I'm currently unable to generate a detailed recommendation because "
                "the AI language model is temporarily unavailable (rate limit reached). "
                "Please try again later."
            )

            yield RAGStreamingChunk(type="content", content=response_text, finish_reason="error")

            citations = [
                Citation(
                    index=i + 1,
                    chunk_id=c.chunk_id,
                    document_title=c.document_title,
                    content_snippet=c.content[:200],
                    score=c.score,
                    rank=c.rank,
                )
                for i, c in enumerate(ctx.chunks[:MAX_CHUNKS_IN_CONTEXT])
            ]
            confidence = self._calculate_confidence(ctx.chunks, ctx.business_summary_text is not None)
            total_latency = (time.perf_counter() - start) * 1000

            yield RAGStreamingChunk(
                type="metadata",
                citations=citations,
                chunk_references=ctx.chunk_refs,
                confidence_score=confidence,
                latency_ms=total_latency,
                model=ctx.model,
                provider="fallback",
                business_summary_version=ctx.business_summary_version,
                conversation_id=request.conversation_id,
            )

    async def _check_escalation(self, request: RAGRequest, response: RAGResponse) -> None:
        if not self._ticket_service:
            return
        if not request.customer_id or not request.store_id:
            return
        if response.confidence_score >= ESCALATION_CONFIDENCE_THRESHOLD:
            return

        user_requested_human = any(
            keyword in request.message.lower()
            for keyword in [
                "talk to a human",
                "talk to human",
                "speak to human",
                "speak to a human",
                "human support",
                "real person",
                "talk to support",
                "contact support",
                "create a ticket",
                "create ticket",
                "open a ticket",
                "open ticket",
                "raise a ticket",
                "raise ticket",
                "escalate",
                "i want to speak",
                "connect me to",
                "transfer me",
            ]
        )

        if not user_requested_human:
            logger.info(
                "Low confidence (%.2f) but user did not request escalation; skipping auto-ticket.",
                response.confidence_score,
            )
            return

        try:
            if await self._ticket_service.has_open_ticket(request.store_id, request.customer_id):
                logger.info(
                    "Skipping escalation for customer %s: an open ticket already exists.",
                    request.customer_id,
                )
                return
        except Exception as exc:
            logger.warning("Open-ticket dedupe check failed: %s", exc, exc_info=True)

        history = []
        if request.conversation_id and self._conversation_service:
            try:
                history = await self._conversation_service.get_conversation_history(
                    request.conversation_id, store_id=request.store_id
                )
            except Exception:
                logger.warning("Failed to load conversation history for escalation check")

        if self._support_agent:
            await self._run_support_agent(request, history)
            return

        try:
            messages_to_analyze = [str(m.content) for m in history] + [request.message]
            ticket = await self._ticket_service.create_ticket(
                TicketCreateDTO(
                    store_id=request.store_id,
                    customer_id=request.customer_id,
                    conversation_id=request.conversation_id,
                    messages=messages_to_analyze,
                )
            )
            logger.info(
                "Auto-escalated ticket %s for customer %s (confidence=%.2f)",
                ticket.id,
                request.customer_id,
                response.confidence_score,
            )
        except Exception as e:
            logger.warning("Failed to auto-escalate ticket: %s", e, exc_info=True)

    async def _run_support_agent(self, request: RAGRequest, history: list) -> None:
        try:
            result = await self._support_agent.run(
                query=request.message,
                store_id=request.store_id,
                customer_id=request.customer_id,
                history=history,
                conversation_id=request.conversation_id,
            )
            if result.escalation_needed:
                logger.info(
                    "Support agent escalated issue %s for customer %s (ticket=%s, priority=%s)",
                    result.issue_category,
                    request.customer_id,
                    result.ticket_id,
                    result.priority,
                )
            else:
                logger.info(
                    "Support agent handled issue '%s' for customer %s without escalation.",
                    result.issue_category,
                    request.customer_id,
                )
        except Exception as exc:
            logger.warning("Support agent escalation failed: %s", exc, exc_info=True)

    def _extract_citations(
        self,
        text: str,
        chunks: list,
    ) -> list[Citation]:
        import re

        citations: list[Citation] = []
        seen: set[int] = set()

        for match in re.finditer(r"\[citation:\s*(\d+)\]", text):
            idx = int(match.group(1))
            if idx in seen:
                continue
            seen.add(idx)

            if 1 <= idx <= len(chunks):
                c = chunks[idx - 1]
                citations.append(
                    Citation(
                        index=idx,
                        chunk_id=c.chunk_id,
                        document_title=c.document_title,
                        content_snippet=c.content[:200],
                        score=c.score,
                        rank=c.rank,
                    )
                )

        return citations

    def _calculate_confidence(
        self,
        chunks: list,
        has_business_summary: bool,
    ) -> float:
        if not chunks:
            return 0.0

        top_k = min(5, len(chunks))
        avg_score = sum(c.score for c in chunks[:top_k]) / top_k

        confidence = 0.3 + 0.7 * avg_score if has_business_summary else 0.2 + 0.8 * avg_score

        return max(0.0, min(1.0, confidence))
