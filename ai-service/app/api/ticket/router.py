from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.ticket.dependencies import get_ticket_service
from app.api.ticket.schemas import (
    DeleteResponseSchema,
    TicketCreateSchema,
    TicketListResponseSchema,
    TicketResponseSchema,
    TicketStatusUpdateSchema,
)
from app.application.ticket.dto.ticket_dto import TicketCreateDTO, TicketStatusUpdateDTO
from app.application.ticket.services.ticket_service import TicketService
from app.domain.ticket.exceptions import TicketNotFoundException

router = APIRouter(prefix="/api/v1/tickets", tags=["Tickets"])


def _handle_exception(exc: Exception) -> None:
    if isinstance(exc, TicketNotFoundException):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("", response_model=TicketResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreateSchema,
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    try:
        result = await service.create_ticket(TicketCreateDTO(**payload.model_dump()))
        return TicketResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/{ticket_id}", response_model=TicketResponseSchema)
async def get_ticket(
    ticket_id: str,
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    try:
        result = await service.get_ticket(ticket_id)
        if result is None:
            raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
        return TicketResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


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
    try:
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
    except Exception as exc:
        _handle_exception(exc)


@router.patch("/{ticket_id}/status", response_model=TicketResponseSchema)
async def update_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdateSchema,
    service: TicketService = Depends(get_ticket_service),
) -> TicketResponseSchema:
    try:
        result = await service.update_status(ticket_id, TicketStatusUpdateDTO(**payload.model_dump()))
        if result is None:
            raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
        return TicketResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.delete("/{ticket_id}", response_model=DeleteResponseSchema)
async def delete_ticket(
    ticket_id: str,
    service: TicketService = Depends(get_ticket_service),
) -> DeleteResponseSchema:
    try:
        from app.infrastructure.mongodb.repositories.ticket_repository import TicketRepository

        repo = TicketRepository()
        success = await repo.delete(ticket_id)
        if not success:
            raise TicketNotFoundException(f"Ticket '{ticket_id}' not found.")
        return DeleteResponseSchema(success=True)
    except Exception as exc:
        _handle_exception(exc)
