import logging

from app.infrastructure.mongodb.collections import get_ticket_analysis_collection

logger = logging.getLogger(__name__)


class SentimentAnalyticsService:
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
            return {"total": 0, "positive_count": 0, "neutral_count": 0, "negative_count": 0}

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
