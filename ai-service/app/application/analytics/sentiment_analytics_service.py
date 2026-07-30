import logging

from app.application.analytics.dto.analytics_dto import SentimentSummaryDTO
from app.domain.ticket.repositories.ticket_repository import TicketRepository
from app.infrastructure.mongodb.collections import get_ticket_analysis_collection
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

    async def get_sentiment_overview(self) -> dict:
        collection = get_ticket_analysis_collection()
        pipeline = [
            {"$match": {"deleted_at": None}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "positive_count": {"$sum": {"$cond": [{"$eq": ["$sentiment", "positive"]}, 1, 0]}},
                    "neutral_count": {"$sum": {"$cond": [{"$eq": ["$sentiment", "neutral"]}, 1, 0]}},
                    "negative_count": {"$sum": {"$cond": [{"$eq": ["$sentiment", "negative"]}, 1, 0]}},
                }
            },
        ]
        cursor = collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        if not result:
            return {
                "total": 0,
                "positive_count": 0,
                "neutral_count": 0,
                "negative_count": 0,
                "positive_pct": 0.0,
                "neutral_pct": 0.0,
                "negative_pct": 0.0,
            }

        row = result[0]
        total = row["total"]
        positive = row["positive_count"]
        neutral = row["neutral_count"]
        negative = row["negative_count"]

        def _pct(val):
            return round(val / total * 100, 1) if total else 0.0

        return {
            "total": total,
            "positive_count": positive,
            "neutral_count": neutral,
            "negative_count": negative,
            "positive_pct": _pct(positive),
            "neutral_pct": _pct(neutral),
            "negative_pct": _pct(negative),
        }
