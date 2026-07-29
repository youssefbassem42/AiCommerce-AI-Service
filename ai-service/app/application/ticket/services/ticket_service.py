import logging
from datetime import datetime, UTC
from typing import List, Optional
from uuid import uuid4

from app.application.services.conversation_service import ConversationService
from app.application.ticket.dto.sentiment_dto import SentimentAnalysisRequest, SentimentAnalysisResult
from app.application.ticket.dto.ticket_dto import (
    ConversationSummaryDTO,
    CustomerProfileDTO,
    LineItemDTO,
    OrderDTO,
    ResolutionMetricsDTO,
    TicketCreateDTO,
    TicketDTO,
    TicketStatusUpdateDTO,
)
from app.application.ticket.services.sentiment_service import SentimentAnalysisService
from app.domain.commerce.repositories.order_repository import OrderRepository
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.domain.ticket.entities.ticket_analysis import TicketAnalysis
from app.domain.ticket.repositories.ticket_repository import TicketRepository

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(
        self,
        ticket_repository: TicketRepository,
        sentiment_service: SentimentAnalysisService,
        conversation_service: Optional[ConversationService] = None,
        order_repository: Optional[OrderRepository] = None,
        customer_repository: Optional[ICustomerRepository] = None,
    ):
        self._ticket_repo = ticket_repository
        self._sentiment = sentiment_service
        self._conversation_service = conversation_service
        self._order_repo = order_repository
        self._customer_repo = customer_repository

    async def create_ticket(self, dto: TicketCreateDTO) -> TicketDTO:
        sentiment_result = await self._sentiment.analyze(
            SentimentAnalysisRequest(
                messages=dto.messages,
                store_id=dto.store_id,
                customer_id=dto.customer_id,
            )
        )

        customer = None
        orders: List[OrderDTO] = []
        conversation: Optional[ConversationSummaryDTO] = None

        if self._customer_repo:
            try:
                customer_entity = await self._customer_repo.find_by_id(dto.customer_id)
                if customer_entity:
                    customer = CustomerProfileDTO(
                        id=customer_entity.id,
                        email=customer_entity.email,
                        first_name=customer_entity.first_name,
                        last_name=customer_entity.last_name,
                        phone=customer_entity.phone,
                    )
            except Exception as e:
                logger.warning("Failed to fetch customer %s: %s", dto.customer_id, e)

        if self._order_repo:
            try:
                order_entities = await self._order_repo.find_by_customer(dto.customer_id, limit=5)
                for oe in order_entities:
                    orders.append(
                        OrderDTO(
                            id=oe.id,
                            total_price=float(oe.total_price.amount) if hasattr(oe.total_price, "amount") else 0.0,
                            currency=oe.currency or "USD",
                            financial_status=oe.financial_status or "unknown",
                            created_at=oe.created_at,
                            line_items=[
                                LineItemDTO(title=li.title, quantity=li.quantity, price=0.0)
                                for li in (oe.line_items or [])
                            ],
                        )
                    )
            except Exception as e:
                logger.warning("Failed to fetch orders for customer %s: %s", dto.customer_id, e)

        if self._conversation_service and dto.conversation_id:
            try:
                history = await self._conversation_service.get_conversation_history(dto.conversation_id)
                conversation = ConversationSummaryDTO(
                    message_count=len(history),
                    recent_messages=[
                        str(m.content)[:200] for m in history[-5:]
                    ],
                )
            except Exception as e:
                logger.warning("Failed to fetch conversation %s: %s", dto.conversation_id, e)

        now = datetime.now(UTC)
        entity = TicketAnalysis(
            id=str(uuid4()),
            ticket_id=str(uuid4()),
            store_id=dto.store_id,
            customer_id=dto.customer_id,
            sentiment=sentiment_result.sentiment,
            category=sentiment_result.category,
            summary=sentiment_result.summary,
            priority=sentiment_result.priority,
            status="open",
            suggested_response=sentiment_result.suggested_response,
            resolution_type="unresolved",
            analyzed_at=now,
        )

        created = await self._ticket_repo.create(entity)

        return self._to_dto(created, customer, orders, conversation)

    async def get_ticket(self, ticket_id: str) -> Optional[TicketDTO]:
        entity = await self._ticket_repo.find_by_ticket_id(ticket_id)
        if entity is None:
            return None

        customer = None
        orders: List[OrderDTO] = []
        conversation: Optional[ConversationSummaryDTO] = None

        if self._customer_repo:
            try:
                customer_entity = await self._customer_repo.find_by_id(entity.customer_id)
                if customer_entity:
                    customer = CustomerProfileDTO(
                        id=customer_entity.id,
                        email=customer_entity.email,
                        first_name=customer_entity.first_name,
                        last_name=customer_entity.last_name,
                        phone=customer_entity.phone,
                    )
            except Exception:
                pass

        return self._to_dto(entity, customer, orders, conversation)

    async def list_tickets(
        self,
        store_id: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        sentiment: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[TicketDTO], int]:
        filters: dict = {"store_id": store_id}
        if status:
            filters["status"] = status
        if priority:
            filters["priority"] = priority
        if sentiment:
            filters["sentiment"] = sentiment

        items, total = await self._ticket_repo.paginate(
            filters=filters,
            page=page,
            page_size=page_size,
        )
        return [self._to_dto(item) for item in items], total

    async def update_status(self, ticket_id: str, dto: TicketStatusUpdateDTO) -> Optional[TicketDTO]:
        entity = await self._ticket_repo.find_by_id(ticket_id)
        if entity is None:
            return None

        entity.status = dto.status
        if dto.resolution_type is not None:
            entity.resolution_type = dto.resolution_type
        elif dto.status in ("resolved", "closed") and entity.resolution_type == "unresolved":
            entity.resolution_type = "ai"

        updated = await self._ticket_repo.update(entity)
        return self._to_dto(updated)

    async def get_resolution_metrics(self, store_id: str) -> ResolutionMetricsDTO:
        all_tickets = await self._ticket_repo.find_many({"store_id": store_id})
        total = len(all_tickets)
        ai_resolved = sum(1 for t in all_tickets if t.resolution_type == "ai")
        human_resolved = sum(1 for t in all_tickets if t.resolution_type == "human")
        unresolved = sum(1 for t in all_tickets if t.resolution_type == "unresolved")
        escalated = sum(1 for t in all_tickets if t.resolution_type == "escalated")
        resolution_rate = (ai_resolved / total * 100) if total > 0 else 0.0

        return ResolutionMetricsDTO(
            store_id=store_id,
            total_tickets=total,
            ai_resolved=ai_resolved,
            human_resolved=human_resolved,
            unresolved=unresolved,
            escalated=escalated,
            resolution_rate=round(resolution_rate, 2),
        )

    @staticmethod
    def _to_dto(
        entity: TicketAnalysis,
        customer: Optional[CustomerProfileDTO] = None,
        orders: Optional[List[OrderDTO]] = None,
        conversation: Optional[ConversationSummaryDTO] = None,
    ) -> TicketDTO:
        return TicketDTO(
            id=entity.id,
            ticket_id=entity.ticket_id,
            store_id=entity.store_id,
            customer_id=entity.customer_id,
            sentiment=entity.sentiment,
            category=entity.category,
            summary=entity.summary,
            priority=entity.priority,
            status=entity.status,
            suggested_response=entity.suggested_response,
            resolution_type=entity.resolution_type,
            analyzed_at=entity.analyzed_at,
            created_at=entity.created_at if hasattr(entity, "created_at") else entity.analyzed_at,
            updated_at=entity.updated_at if hasattr(entity, "updated_at") else entity.analyzed_at,
            customer=customer,
            recent_orders=orders or [],
            conversation=conversation,
        )
