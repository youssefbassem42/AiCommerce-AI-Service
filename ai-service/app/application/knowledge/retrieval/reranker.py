import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.application.knowledge.retrieval.dto import RetrievedChunkDTO
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class ReRanker(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[RetrievedChunkDTO],
        top_k: int,
    ) -> list[RetrievedChunkDTO]:
        pass


class LLMCrossEncoderReRanker(ReRanker):
    RERANK_SYSTEM_PROMPT = (
        "You are a relevance scorer. For the given query, score each document "
        "on a scale of 0.0 to 1.0 based on relevance. Return ONLY a JSON array "
        'of objects with "score" (float) and "index" (int) fields, ordered by score descending.'
    )

    def __init__(
        self,
        provider: BaseLLMProvider,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_chars_per_doc: int = 1500,
    ):
        self._provider = provider
        self._model = model
        self._temperature = temperature
        self._max_chars_per_doc = max_chars_per_doc

    async def rerank(
        self,
        query: str,
        documents: list[RetrievedChunkDTO],
        top_k: int,
    ) -> list[RetrievedChunkDTO]:
        if not documents:
            return []

        if len(documents) <= 1:
            return documents[:top_k]

        user_content = f"Query: {query}\n\nDocuments:\n"
        for i, doc in enumerate(documents):
            truncated = doc.content[:self._max_chars_per_doc]
            user_content += f"\n[{i}] {truncated}\n"

        request = ChatRequest(
            messages=[
                MessageDTO(role="system", content=self.RERANK_SYSTEM_PROMPT),
                MessageDTO(role="user", content=user_content),
            ],
            model=self._model,
            temperature=self._temperature,
            json_mode=True,
        )

        response = await self._provider.chat(request)
        raw = response.message.content
        if isinstance(raw, list):
            raw = " ".join(str(item) for item in raw)

        scores = self._parse_scores(raw, len(documents))

        reranked = []
        for item in scores:
            idx = item.get("index")
            score = item.get("score", 0.0)
            if idx is not None and 0 <= idx < len(documents):
                doc = documents[idx]
                doc.score = score
                reranked.append(doc)

        seen = {id(d) for d in reranked}
        for doc in documents:
            if id(doc) not in seen:
                doc.score = 0.0
                reranked.append(doc)

        reranked.sort(key=lambda d: d.score, reverse=True)
        for i, doc in enumerate(reranked):
            doc.rank = i + 1

        return reranked[:top_k]

    def _parse_scores(self, raw: str, expected_count: int) -> list[dict]:
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json")
        if cleaned.endswith("```"):
            cleaned = cleaned.removesuffix("```")
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed[:expected_count]
            if isinstance(parsed, dict):
                return parsed.get("scores", parsed.get("results", []))[:expected_count]
        except json.JSONDecodeError:
            logger.warning("Re-ranker LLM returned non-JSON response, using original scores")

        return [{"index": i, "score": 0.0} for i in range(expected_count)]
