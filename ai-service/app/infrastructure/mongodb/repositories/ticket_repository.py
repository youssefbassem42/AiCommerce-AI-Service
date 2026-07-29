from typing import List, Optional, Any
import logging

from app.domain.ticket.entities.ticket_analysis import TicketAnalysis
from app.domain.ticket.repositories.ticket_repository import TicketRepository as ITicketRepository
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository
from app.infrastructure.mongodb.documents.ticket_document import TicketAnalysisDocument
from app.infrastructure.mongodb.collections import get_ticket_analysis_collection

logger = logging.getLogger(__name__)

class TicketRepository(BaseMongoRepository[TicketAnalysisDocument, TicketAnalysis], ITicketRepository):
    """MongoDB implementation of the TicketRepository with session and transaction support."""

    def __init__(self):
        super().__init__(get_ticket_analysis_collection(), TicketAnalysisDocument)

    async def find_by_ticket_id(self, ticket_id: str, session: Any = None) -> Optional[TicketAnalysis]:
        """Fetch analysis report by ticket ID."""
        try:
            results = await self.find_many({"ticket_id": ticket_id}, limit=1, session=session)
            return results[0] if results else None
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def find_by_store(
        self, store_id: str, priority: Optional[str] = None, session: Any = None
    ) -> List[TicketAnalysis]:
        """Fetch ticket analysis records for a store, optionally filtered by priority."""
        try:
            filters = {"store_id": store_id}
            if priority:
                filters["priority"] = priority
            return await self.find_many(filters, session=session)
        except Exception as e:
            self._handle_db_error(e)
            raise
