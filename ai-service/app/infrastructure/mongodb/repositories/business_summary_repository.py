from app.domain.knowledge.entities.business_summary import BusinessSummary
from app.domain.knowledge.repositories.business_summary_repository import (
    BusinessSummaryRepository as IBusinessSummaryRepository,
)
from app.infrastructure.mongodb.collections import get_knowledge_business_summaries_collection
from app.infrastructure.mongodb.documents.business_summary_document import BusinessSummaryDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class BusinessSummaryRepository(
    BaseMongoRepository[BusinessSummaryDocument, BusinessSummary],
    IBusinessSummaryRepository,
):
    """MongoDB implementation of the business summary repository."""

    def __init__(self):
        super().__init__(get_knowledge_business_summaries_collection(), BusinessSummaryDocument)

    async def find_by_document_id(
        self,
        document_id: str,
        version_number: int | None = None,
        limit: int = 100,
        skip: int = 0,
        session=None,
    ) -> list[BusinessSummary]:
        filters: dict[str, str | int] = {"document_id": document_id}
        if version_number is not None:
            filters["version_number"] = version_number
        return await self.find_many(filters=filters, limit=limit, skip=skip, session=session)
