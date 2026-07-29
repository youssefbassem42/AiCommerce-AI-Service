import json
import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.application.knowledge.generation.config import GenerationConfig
from app.application.knowledge.generation.prompt_builder import (
    SECTION_DEFINITIONS,
    build_generation_messages,
)
from app.domain.knowledge.entities.business_summary import BusinessSummary
from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument
from app.domain.knowledge.exceptions import ChunkingException
from app.domain.knowledge.repositories.business_summary_repository import (
    BusinessSummaryRepository,
)
from app.domain.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

BUSINESS_CONTEXT_TITLE_PREFIX = "Business Context"


class BusinessSummaryGenerationService:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        summary_repository: BusinessSummaryRepository,
        provider: BaseLLMProvider,
    ):
        self.knowledge_repository = knowledge_repository
        self.summary_repository = summary_repository
        self.provider = provider

    async def generate(
        self,
        store_id: str,
        config: GenerationConfig | None = None,
    ) -> BusinessSummary:
        cfg = config or GenerationConfig()
        documents = await self._load_documents(store_id)
        merged = self._merge_documents(documents)

        version = await self._next_version(store_id)
        sections = await self._call_llm(merged, cfg, store_id)
        rag_context = sections.pop("rag_context", "")
        title = f"{BUSINESS_CONTEXT_TITLE_PREFIX} v{version}"

        entity = BusinessSummary(
            id=str(ObjectId()),
            document_id=store_id,
            version_number=version,
            title=title,
            summary=rag_context or self._build_fallback_context(sections),
            metadata={
                "version": version,
                "store_id": store_id,
                "sections": sections,
                "document_ids_used": [doc.id for doc in documents],
                "document_count": len(documents),
                "document_titles": [doc.title for doc in documents],
                "generated_at": datetime.now(UTC).isoformat(),
                "model": cfg.model,
                "temperature": cfg.temperature,
            },
        )
        created = await self.summary_repository.create(entity)
        logger.info(
            "Business context generated for store '%s' v%d (%d sections, %d documents)",
            store_id, version, len(sections), len(documents),
        )
        return created

    async def regenerate(
        self,
        store_id: str,
        config: GenerationConfig | None = None,
    ) -> BusinessSummary:
        return await self.generate(store_id, config)

    async def _load_documents(self, store_id: str) -> list[KnowledgeDocument]:
        docs = await self.knowledge_repository.find_by_store_id(store_id, limit=500)
        approved = [
            d for d in docs
            if d.status == "active" and d.processed_text
        ]
        if not approved:
            raise ChunkingException(
                f"No approved documents with processed text found for store '{store_id}'"
            )
        return approved

    def _merge_documents(self, documents: list[KnowledgeDocument], max_chars: int = 100_000) -> str:
        parts = []
        total = 0
        for doc in documents:
            text = doc.processed_text or ""
            header = f"=== {doc.title} ===\n\n"
            combined = header + text + "\n\n"
            if total + len(combined) > max_chars:
                remaining = max_chars - total
                if remaining > 100:
                    parts.append(combined[:remaining])
                break
            parts.append(combined)
            total += len(combined)
        return "".join(parts)

    async def _next_version(self, store_id: str) -> int:
        existing = await self.summary_repository.find_by_document_id(
            store_id, limit=1_000
        )
        if not existing:
            return 1
        return max(s.version_number for s in existing) + 1

    async def _call_llm(
        self, merged_content: str, cfg: GenerationConfig, store_id: str
    ) -> dict[str, str]:
        raw_messages = build_generation_messages(merged_content)
        messages = [
            MessageDTO(role=m["role"], content=m["content"]) for m in raw_messages
        ]

        request = ChatRequest(
            messages=messages,
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            json_mode=True,
        )
        response = await self.provider.chat(request)
        raw = response.message.content
        if isinstance(raw, list):
            raw = " ".join(str(item) for item in raw)

        return self._parse_response(raw, store_id, cfg)

    def _parse_response(self, raw: str, store_id: str, cfg: GenerationConfig) -> dict[str, str]:
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json")
        if cleaned.endswith("```"):
            cleaned = cleaned.removesuffix("```")
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM response was not valid JSON for store '%s'", store_id)
            return {"rag_context": cleaned}

        if not isinstance(parsed, dict):
            return {"rag_context": str(parsed)}

        parsed = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in parsed.items()}
        expected = set(SECTION_DEFINITIONS.keys()) | {"rag_context"}
        missing = expected - set(parsed.keys())
        if missing:
            logger.warning("LLM response missing sections %s for store '%s'", missing, store_id)

        return parsed

    def _build_fallback_context(self, sections: dict[str, str]) -> str:
        parts = []
        for key, desc in SECTION_DEFINITIONS.items():
            content = sections.get(key, "")
            if content:
                parts.append(f"{key.replace('_', ' ').title()}\n{content}")
        return "\n\n".join(parts)
