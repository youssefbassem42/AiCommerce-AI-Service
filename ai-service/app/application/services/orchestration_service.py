"""Orchestration Service: wires the coordinator agent, sub-agents, memory agent, and conversation workflow."""

import logging
from typing import Any

from app.agents.coordinator.agent import CoordinatorAgent
from app.agents.memory.agent import MemoryAgent
from app.application.dto.ai_dto import ChatResponse
from app.application.recommendation.services import BundleSuggestionService, RecommendationService
from app.application.services.conversation_service import ConversationService
from app.domain.memory.repositories.memory_repository import MemoryRepository
from app.infrastructure.mongodb.repositories.conversation_repository import (
    ConversationRepository as MongoConversationRepository,
)
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.workflows.conversation.graph import ConversationWorkflow

logger = logging.getLogger(__name__)


class OrchestrationService:
    """Builds and runs the Phase 01 orchestration stack for AI chat traffic."""

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        conversation_service: ConversationService | None = None,
        memory_repo: MemoryRepository | None = None,
        recommendation_service: RecommendationService | None = None,
        bundle_service: BundleSuggestionService | None = None,
        llm: BaseLLMProvider | None = None,
    ):
        self._provider_factory = provider_factory
        self._conversation_service = conversation_service
        self._memory_repo = memory_repo
        self._recommendation_service = recommendation_service
        self._bundle_service = bundle_service
        self._llm = llm or LLMProviderFactory().get_provider("openrouter")
        self._workflow: ConversationWorkflow | None = None

    @property
    def workflow(self) -> ConversationWorkflow:
        if self._workflow is None:
            self._workflow = self._build_workflow()
        return self._workflow

    def _build_workflow(self) -> ConversationWorkflow:
        conversation_repo = MongoConversationRepository()

        sub_agents: dict[str, Any] = {}
        if self._recommendation_service:
            sub_agents["recommendation"] = self._recommendation_service.recommend
        if self._bundle_service:
            sub_agents["bundle"] = self._bundle_service.suggest

        coordinator = CoordinatorAgent(
            llm=self._llm,
            conversation_repo=conversation_repo,
            sub_agents=sub_agents,
        )

        memory_agent = MemoryAgent(
            memory_repo=self._memory_repo,
            llm=self._llm,
        )

        return ConversationWorkflow(
            coordinator=coordinator,
            llm=self._llm,
            sub_agents=sub_agents,
            memory_agent=memory_agent,
        )

    async def chat(
        self,
        user_input: str,
        store_id: str,
        customer_id: str | None = None,
        conversation_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """Run a chat turn through the coordinator + conversation workflow."""
        return await self.workflow.run(
            user_input=user_input,
            store_id=store_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            history=history,
            metadata=metadata,
        )
