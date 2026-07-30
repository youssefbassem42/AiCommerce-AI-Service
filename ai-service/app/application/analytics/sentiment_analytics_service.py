import logging

from app.application.analytics.dto.analytics_dto import SentimentSummaryDTO
from app.domain.ticket.repositories.ticket_repository import TicketRepository
from app.infrastructure.mongodb.repositories.ticket_repository import TicketRepository as MongoTicketRepository

logger = logging.getLogger(__name__)


class SentimentAnalyticsService:
    def __init__(self, ticket_repository: TicketRepository | None = None):
        self._ticket_repo = ticket_repository or MongoTicketRepository()

    async def get_sentiment_summary(self, store_id: str) -> SentimentSummaryDTO:
        tickets = await self._ticket_repo.find_many({"store_id": store_id})
        total = len(tickets)

        positive = sum(1 for t in tickets if t.sentiment == "positive")
        neutral = sum(1 for t in tickets if t.sentiment == "neutral")
        negative = sum(1 for t in tickets if t.sentiment == "negative")

        def pct(count: int) -> float:
            return round(count / total * 100, 1) if total > 0 else 0.0

        return SentimentSummaryDTO(
            store_id=store_id,
            total=total,
            positive_count=positive,
            neutral_count=neutral,
            negative_count=negative,
            positive_pct=pct(positive),
            neutral_pct=pct(neutral),
            negative_pct=pct(negative),
        )
