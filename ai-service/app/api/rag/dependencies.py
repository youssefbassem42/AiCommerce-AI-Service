from fastapi import Depends

from app.agents.escalation.agent import EscalationAgent
from app.agents.support.agent import SupportAgent
from app.api.ai.dependencies import (
    get_ai_service,
    get_conversation_service,
    get_customer_repository,
    get_order_repository,
    get_provider,
)
from app.api.knowledge.retrieval_dependencies import get_retriever_service
from app.api.ticket.dependencies import get_notification_service, get_ticket_service
from app.application.knowledge.retrieval.service import RetrieverService
from app.application.rag.service import RagOrchestrationService
from app.application.services.chat_service import ChatService
from app.application.services.conversation_service import ConversationService
from app.application.ticket.services.notification_service import TicketNotificationService
from app.application.ticket.services.ticket_service import TicketService
from app.domain.commerce.repositories.order_repository import OrderRepository
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.domain.knowledge.repositories.business_summary_repository import BusinessSummaryRepository
from app.infrastructure.mongodb.repositories.business_summary_repository import BusinessSummaryRepository
from app.infrastructure.providers.base import BaseLLMProvider


def get_summary_repository() -> BusinessSummaryRepository:
    return BusinessSummaryRepository()


def get_escalation_agent(
    llm: BaseLLMProvider = Depends(get_provider),
    ticket_service: TicketService = Depends(get_ticket_service),
    notification_service: TicketNotificationService = Depends(get_notification_service),
    customer_repo: ICustomerRepository = Depends(get_customer_repository),
) -> EscalationAgent:
    return EscalationAgent(
        llm=llm,
        ticket_service=ticket_service,
        notification_service=notification_service,
        customer_repo=customer_repo,
    )


def get_support_agent(
    llm: BaseLLMProvider = Depends(get_provider),
    customer_repo: ICustomerRepository = Depends(get_customer_repository),
    order_repo: OrderRepository = Depends(get_order_repository),
    ticket_service: TicketService = Depends(get_ticket_service),
    escalation_agent: EscalationAgent = Depends(get_escalation_agent),
) -> SupportAgent:
    return SupportAgent(
        llm=llm,
        customer_repo=customer_repo,
        order_repo=order_repo,
        ticket_service=ticket_service,
        escalation_agent=escalation_agent,
    )


async def get_rag_service(
    retriever_service: RetrieverService = Depends(get_retriever_service),
    chat_service: ChatService = Depends(get_ai_service),
    conversation_service: ConversationService = Depends(get_conversation_service),
    summary_repo: BusinessSummaryRepository = Depends(get_summary_repository),
    ticket_service: TicketService = Depends(get_ticket_service),
    support_agent: SupportAgent = Depends(get_support_agent),
) -> RagOrchestrationService:
    return RagOrchestrationService(
        retriever_service=retriever_service,
        chat_service=chat_service,
        conversation_service=conversation_service,
        business_summary_repository=summary_repo,
        ticket_service=ticket_service,
        support_agent=support_agent,
    )
