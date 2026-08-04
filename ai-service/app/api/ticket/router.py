from fastapi import APIRouter, Depends, Query, status

from app.api.ticket.dependencies import get_notification_service, get_ticket_service
from app.api.ticket.schemas import (
    AddMessageSchema,
    DeleteResponseSchema,
    EscalateTicketSchema,
    ResolutionMetricsResponseSchema,
    ResolveTicketSchema,
    TicketCreateSchema,
    TicketListResponseSchema,
    TicketNotificationListSchema,
    TicketResponseSchema,
    TicketStatusUpdateSchema,
)
from app.application.ticket.dto.ticket_dto import TicketCreateDTO, TicketStatusUpdateDTO
from app.application.ticket.services.notification_service import TicketNotificationService
from app.application.ticket.services.ticket_service import TicketService
from app.domain.ticket.exceptions import TicketNotFoundException

router = APIRouter(prefix="/api/v1/tickets", tags=["Tickets"])


@router.post("", response_model=TicketResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreateSchema,
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.create_ticket(TicketCreateDTO(**payload.model_dump()))
    return TicketResponseSchema(**result.model_dump())


@router.get("/{ticket_id}", response_model=TicketResponseSchema)
async def get_ticket(
    ticket_id: str,
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.get_ticket(ticket_id)
    if result is None:
        raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
    return TicketResponseSchema(**result.model_dump())


@router.get("", response_model=TicketListResponseSchema)
async def list_tickets(
    store_id: str = Query(...),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: TicketService = Depends(get_ticket_service),
) -> TicketListResponseSchema:
    items, total = await service.list_tickets(
        store_id=store_id,
        status=status,
        priority=priority,
        sentiment=sentiment,
        page=page,
        page_size=page_size,
    )
    return TicketListResponseSchema(
        items=[TicketResponseSchema(**item.model_dump()) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/metrics/resolution", response_model=ResolutionMetricsResponseSchema)
async def get_resolution_metrics(
    store_id: str = Query(...),
    service: TicketService = Depends(get_ticket_service),
) -> ResolutionMetricsResponseSchema:
    result = await service.get_resolution_metrics(store_id)
    return ResolutionMetricsResponseSchema(**result.model_dump())


@router.patch("/{ticket_id}/status", response_model=TicketResponseSchema)
async def update_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdateSchema,
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.update_status(ticket_id, TicketStatusUpdateDTO(**payload.model_dump()))
    if result is None:
        raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
    return TicketResponseSchema(**result.model_dump())


@router.post("/{ticket_id}/messages", response_model=TicketResponseSchema)
async def add_ticket_message(
    ticket_id: str,
    payload: AddMessageSchema,
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.add_message(
        ticket_id=ticket_id,
        sender=payload.sender,
        content=payload.content,
    )
    if result is None:
        raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
    return TicketResponseSchema(**result.model_dump())


@router.post("/{ticket_id}/resolve", response_model=TicketResponseSchema)
async def resolve_ticket(
    ticket_id: str,
    payload: ResolveTicketSchema,
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.resolve_ticket(
        ticket_id=ticket_id,
        resolution_type=payload.resolution_type,
        message=payload.message,
    )
    if result is None:
        raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
    return TicketResponseSchema(**result.model_dump())


@router.post("/{ticket_id}/escalate", response_model=TicketResponseSchema)
async def escalate_ticket(
    ticket_id: str,
    payload: EscalateTicketSchema,
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.escalate_ticket(
        ticket_id=ticket_id,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        eta=payload.eta,
        message=payload.message,
    )
    if result is None:
        raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
    return TicketResponseSchema(**result.model_dump())


@router.get("/{ticket_id}/notifications", response_model=TicketNotificationListSchema)
async def list_ticket_notifications(
    ticket_id: str,
    customer_id: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    service: TicketNotificationService = Depends(get_notification_service),
) -> TicketNotificationListSchema:
    items = await service.list_notifications(
        ticket_id=ticket_id,
        customer_id=customer_id,
        unread_only=unread_only,
        limit=limit,
    )
    unread = len(
        await service.list_notifications(
            ticket_id=ticket_id,
            customer_id=customer_id,
            unread_only=True,
            limit=200,
        )
    )
    return TicketNotificationListSchema(
        items=[TicketNotificationSchema(**i) for i in items],
        total=len(items),
        unread=unread,
    )


@router.delete("/{ticket_id}", response_model=DeleteResponseSchema)
async def delete_ticket(
    ticket_id: str,
    service: TicketService = Depends(get_ticket_service),
) -> DeleteResponseSchema:
    from app.infrastructure.mongodb.repositories.ticket_repository import TicketRepository

    repo = TicketRepository()
    success = await repo.delete(ticket_id)
    if not success:
        raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
    return DeleteResponseSchema(success=True)
