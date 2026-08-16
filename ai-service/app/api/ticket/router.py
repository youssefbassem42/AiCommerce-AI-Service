from fastapi import APIRouter, Depends, Query, status

from app.api.auth.dependencies import get_current_store_id, require_admin_role
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
    TicketNotificationSchema,
    TicketResponseSchema,
    TicketStatusUpdateSchema,
)
from app.application.ticket.dto.ticket_dto import TicketCreateDTO, TicketDTO, TicketStatusUpdateDTO
from app.application.ticket.services.notification_service import TicketNotificationService
from app.application.ticket.services.ticket_service import TicketService
from app.domain.ticket.exceptions import TicketNotFoundException

router = APIRouter(
    prefix="/api/v1/tickets",
    tags=["Tickets"],
    dependencies=[Depends(require_admin_role)],
)


def _assert_ticket_store_owned(ticket: TicketDTO | None, store_id: str) -> None:
    """Ticket endpoints are store-admin scoped: a ticket from another store is
    never readable or mutable (tenant isolation, matching commerce endpoints)."""
    if ticket is None or ticket.store_id != store_id:
        raise TicketNotFoundException("Ticket not found.")


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
    store_id: str = Depends(get_current_store_id),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.get_ticket(ticket_id)
    _assert_ticket_store_owned(result, store_id)
    return TicketResponseSchema(**result.model_dump())


@router.get("", response_model=TicketListResponseSchema)
async def list_tickets(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store_id: str = Depends(get_current_store_id),
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
    store_id: str = Depends(get_current_store_id),
    service: TicketService = Depends(get_ticket_service),
) -> ResolutionMetricsResponseSchema:
    result = await service.get_resolution_metrics(store_id)
    return ResolutionMetricsResponseSchema(**result.model_dump())


@router.patch("/{ticket_id}/status", response_model=TicketResponseSchema)
async def update_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdateSchema,
    store_id: str = Depends(get_current_store_id),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.update_status(ticket_id, TicketStatusUpdateDTO(**payload.model_dump()))
    _assert_ticket_store_owned(result, store_id)
    return TicketResponseSchema(**result.model_dump())


@router.post("/{ticket_id}/messages", response_model=TicketResponseSchema)
async def add_ticket_message(
    ticket_id: str,
    payload: AddMessageSchema,
    store_id: str = Depends(get_current_store_id),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.add_message(
        ticket_id=ticket_id,
        sender=payload.sender,
        content=payload.content,
    )
    _assert_ticket_store_owned(result, store_id)
    return TicketResponseSchema(**result.model_dump())


@router.post("/{ticket_id}/resolve", response_model=TicketResponseSchema)
async def resolve_ticket(
    ticket_id: str,
    payload: ResolveTicketSchema,
    store_id: str = Depends(get_current_store_id),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.resolve_ticket(
        ticket_id=ticket_id,
        resolution_type=payload.resolution_type,
        message=payload.message,
    )
    _assert_ticket_store_owned(result, store_id)
    return TicketResponseSchema(**result.model_dump())


@router.post("/{ticket_id}/escalate", response_model=TicketResponseSchema)
async def escalate_ticket(
    ticket_id: str,
    payload: EscalateTicketSchema,
    store_id: str = Depends(get_current_store_id),
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    result = await service.escalate_ticket(
        ticket_id=ticket_id,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        eta=payload.eta,
        message=payload.message,
    )
    _assert_ticket_store_owned(result, store_id)
    return TicketResponseSchema(**result.model_dump())


@router.get("/{ticket_id}/notifications", response_model=TicketNotificationListSchema)
async def list_ticket_notifications(
    ticket_id: str,
    store_id: str = Depends(get_current_store_id),
    customer_id: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    service: TicketService = Depends(get_ticket_service),
    notification_service: TicketNotificationService = Depends(get_notification_service),
) -> TicketNotificationListSchema:
    ticket = await service.get_ticket(ticket_id)
    _assert_ticket_store_owned(ticket, store_id)
    items = await notification_service.list_notifications(
        ticket_id=ticket_id,
        customer_id=customer_id,
        unread_only=unread_only,
        limit=limit,
    )
    unread = len(
        await notification_service.list_notifications(
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
    store_id: str = Depends(get_current_store_id),
    service: TicketService = Depends(get_ticket_service),
) -> DeleteResponseSchema:
    from app.infrastructure.mongodb.repositories.ticket_repository import TicketRepository

    existing = await service.get_ticket(ticket_id)
    _assert_ticket_store_owned(existing, store_id)
    repo = TicketRepository()
    success = await repo.delete(ticket_id)
    if not success:
        raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
    return DeleteResponseSchema(success=True)
