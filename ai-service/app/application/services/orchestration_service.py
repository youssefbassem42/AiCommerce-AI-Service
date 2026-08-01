"""Orchestration Service: wires the coordinator agent, sub-agents, memory agent, and conversation workflow."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.agents.coordinator.agent import CoordinatorAgent
from app.agents.memory.agent import MemoryAgent
from app.application.dto.ai_dto import ChatResponse
from app.application.recommendation.promo_service import PromoCodeService
from app.application.recommendation.services import BundleSuggestionService, RecommendationService
from app.application.services.conversation_service import ConversationService
from app.domain.commerce.repositories.order_repository import OrderRepository
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.domain.memory.repositories.memory_repository import MemoryRepository
from app.infrastructure.mongodb.repositories.conversation_repository import (
    ConversationRepository as MongoConversationRepository,
)
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.workflows.conversation.graph import ConversationWorkflow

if TYPE_CHECKING:
    # Imported lazily at runtime to avoid a circular import chain:
    # orchestration -> ticket services -> chat_service -> orchestration.
    from app.application.ticket.services.notification_service import TicketNotificationService
    from app.application.ticket.services.ticket_service import TicketService

logger = logging.getLogger(__name__)


class OrchestrationService:
    """Builds and runs the orchestration stack for AI chat traffic."""

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        conversation_service: ConversationService | None = None,
        memory_repo: MemoryRepository | None = None,
        recommendation_service: RecommendationService | None = None,
        bundle_service: BundleSuggestionService | None = None,
        llm: BaseLLMProvider | None = None,
        customer_repo: ICustomerRepository | None = None,
        order_repo: OrderRepository | None = None,
        ticket_service: TicketService | None = None,
        notification_service: TicketNotificationService | None = None,
        promo_service: PromoCodeService | None = None,
    ):
        self._provider_factory = provider_factory
        self._conversation_service = conversation_service
        self._memory_repo = memory_repo
        self._recommendation_service = recommendation_service
        self._bundle_service = bundle_service
        self._customer_repo = customer_repo
        self._order_repo = order_repo
        self._ticket_service = ticket_service
        self._notification_service = notification_service
        self._promo_service = promo_service
        self._llm = llm or LLMProviderFactory().get_provider("openrouter")
        self._workflow: ConversationWorkflow | None = None

    @property
    def workflow(self) -> ConversationWorkflow:
        if self._workflow is None:
            self._workflow = self._build_workflow()
        return self._workflow

    def _build_workflow(self) -> ConversationWorkflow:
        # Lazy imports to avoid a circular import chain:
        # orchestration -> agents -> ticket services -> chat_service -> orchestration.
        from app.agents.escalation.agent import EscalationAgent
        from app.agents.sales.agent import SalesAgent
        from app.agents.support.agent import SupportAgent

        conversation_repo = MongoConversationRepository()

        sub_agents: dict[str, Any] = {}
        if self._recommendation_service:
            sub_agents["recommendation"] = self._recommendation_service.recommend
        if self._bundle_service:
            sub_agents["bundle"] = self._bundle_service.suggest

        sales_agent = None
        support_agent = None
        escalation_agent = None

        if self._recommendation_service:
            sales_agent = SalesAgent(
                llm=self._llm,
                recommendation_service=self._recommendation_service,
                promo_service=self._promo_service,
            )
            sub_agents["sales"] = sales_agent.run

        escalation_agent = EscalationAgent(
            llm=self._llm,
            ticket_service=self._ticket_service,
            notification_service=self._notification_service,
            customer_repo=self._customer_repo,
        )

        support_agent = SupportAgent(
            llm=self._llm,
            customer_repo=self._customer_repo,
            order_repo=self._order_repo,
            ticket_service=self._ticket_service,
            escalation_agent=escalation_agent,
        )
        sub_agents["support"] = support_agent.run
        sub_agents["escalation"] = escalation_agent.run

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
