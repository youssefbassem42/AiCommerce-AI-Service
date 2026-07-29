from fastapi import Depends

from app.api.ai.dependencies import get_ai_service, get_conversation_service
from app.application.services.chat_service import ChatService
from app.application.services.conversation_service import ConversationService
from app.application.ticket.services.sentiment_service import SentimentAnalysisService
from app.application.ticket.services.ticket_service import TicketService
from app.domain.commerce.repositories.order_repository import OrderRepository
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.infrastructure.mongodb.repositories.commerce_order_repository import CommerceOrderRepository
from app.infrastructure.mongodb.repositories.customer_repository import CustomerMongoRepository
from app.infrastructure.mongodb.repositories.ticket_repository import TicketRepository


def get_ticket_repository() -> TicketRepository:
    return TicketRepository()


def get_order_repository() -> OrderRepository:
    return CommerceOrderRepository()


def get_customer_repository() -> ICustomerRepository:
    return CustomerMongoRepository()


def get_sentiment_service(
    chat_service: ChatService = Depends(get_ai_service),
) -> SentimentAnalysisService:
    return SentimentAnalysisService(chat_service=chat_service)


def get_ticket_service(
    ticket_repo: TicketRepository = Depends(get_ticket_repository),
    sentiment_service: SentimentAnalysisService = Depends(get_sentiment_service),
    conversation_service: ConversationService = Depends(get_conversation_service),
    order_repo: OrderRepository = Depends(get_order_repository),
    customer_repo: ICustomerRepository = Depends(get_customer_repository),
) -> TicketService:
    return TicketService(
        ticket_repository=ticket_repo,
        sentiment_service=sentiment_service,
        conversation_service=conversation_service,
        order_repository=order_repo,
        customer_repository=customer_repo,
    )
