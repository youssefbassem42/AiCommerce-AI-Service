import logging

from app.application.knowledge.dto.knowledge_dto import BusinessSummaryDTO, PaginatedResultDTO
from app.application.knowledge.queries.list_business_summary_history_query import (
    ListBusinessSummaryHistoryQuery,
)
from app.domain.knowledge.repositories.business_summary_repository import (
    BusinessSummaryRepository,
)

logger = logging.getLogger(__name__)


class ListBusinessSummaryHistoryHandler:
    def __init__(self, repository: BusinessSummaryRepository):
        self.repository = repository

    async def handle(
        self, query: ListBusinessSummaryHistoryQuery
    ) -> PaginatedResultDTO[BusinessSummaryDTO]:
        items, total = await self.repository.paginate(
            filters={"document_id": query.store_id},
            page=query.page,
            page_size=query.page_size,
        )
        return PaginatedResultDTO(
            items=[BusinessSummaryDTO(**item.model_dump()) for item in items],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
