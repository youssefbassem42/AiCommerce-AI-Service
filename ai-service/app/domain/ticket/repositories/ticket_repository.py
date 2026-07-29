from abc import ABC, abstractmethod
from typing import List, Optional
from app.shared.kernel.repository import AsyncRepository
from app.domain.ticket.entities.ticket_analysis import TicketAnalysis

class TicketRepository(AsyncRepository[TicketAnalysis, str], ABC):
    """Domain repository interface for Ticket Analysis Context."""

    @abstractmethod
    async def find_by_ticket_id(self, ticket_id: str) -> Optional[TicketAnalysis]:
        """Fetch analysis report by ticket ID."""
        pass

    @abstractmethod
    async def find_by_store(self, store_id: str, priority: Optional[str] = None) -> List[TicketAnalysis]:
        """Fetch ticket analysis records for a store, optionally filtered by priority."""
        pass
