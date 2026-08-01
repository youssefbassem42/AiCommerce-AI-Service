from abc import ABC, abstractmethod

from app.domain.ticket.entities.ticket_analysis import TicketAnalysis
from app.shared.kernel.repository import AsyncRepository


class TicketRepository(AsyncRepository[TicketAnalysis, str], ABC):
    """Domain repository interface for Ticket Analysis Context."""

    @abstractmethod
    async def find_by_ticket_id(self, ticket_id: str) -> TicketAnalysis | None:
        """Fetch analysis report by ticket ID."""
        pass

    @abstractmethod
    async def find_by_store(self, store_id: str, priority: str | None = None) -> list[TicketAnalysis]:
        """Fetch ticket analysis records for a store, optionally filtered by priority."""
        pass

    @abstractmethod
    async def find_open_by_customer(self, store_id: str, customer_id: str) -> TicketAnalysis | None:
        """Fetch the most recent open ticket for a customer in a store."""
        pass
