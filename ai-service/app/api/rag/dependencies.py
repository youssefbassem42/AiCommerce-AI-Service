from fastapi import Depends

from app.api.ai.dependencies import get_ai_service, get_conversation_service
from app.api.knowledge.retrieval_dependencies import get_retriever_service
from app.api.ticket.dependencies import get_ticket_service
from app.application.knowledge.retrieval.service import RetrieverService
from app.application.rag.service import RagOrchestrationService
from app.application.services.chat_service import ChatService
from app.application.services.conversation_service import ConversationService
from app.application.ticket.services.ticket_service import TicketService
from app.domain.knowledge.repositories.business_summary_repository import BusinessSummaryRepository
from app.infrastructure.mongodb.repositories.business_summary_repository import BusinessSummaryRepository


def get_summary_repository() -> BusinessSummaryRepository:
    return BusinessSummaryRepository()


async def get_rag_service(
    retriever_service: RetrieverService = Depends(get_retriever_service),
    chat_service: ChatService = Depends(get_ai_service),
    conversation_service: ConversationService = Depends(get_conversation_service),
    summary_repo: BusinessSummaryRepository = Depends(get_summary_repository),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> RagOrchestrationService:
    return RagOrchestrationService(
        retriever_service=retriever_service,
        chat_service=chat_service,
        conversation_service=conversation_service,
        business_summary_repository=summary_repo,
        ticket_service=ticket_service,
    )
