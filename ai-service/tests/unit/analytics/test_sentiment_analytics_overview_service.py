import pytest

from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService


class FakeCursor:
    def __init__(self, results):
        self._results = results

    async def to_list(self, length):
        return self._results[:length] if length else self._results


class FakeCollection:
    def __init__(self, results):
        self._results = results
        self.aggregate_calls = []

    def aggregate(self, pipeline):
        self.aggregate_calls.append(pipeline)
        return FakeCursor(self._results)


@pytest.fixture
def collection(monkeypatch):
    fake = FakeCollection([])
    monkeypatch.setattr(
        "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
        lambda: fake,
    )
    return fake


@pytest.fixture
def service():
    return SentimentAnalyticsService()


class TestSentimentAnalyticsOverviewService:
    async def test_empty_collection_returns_zeros(self, service, collection):
        result = await service.get_sentiment_overview()

        assert result == {
            "total": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "positive_pct": 0.0,
            "neutral_pct": 0.0,
            "negative_pct": 0.0,
        }

    async def test_mixed_sentiments_returns_counts_and_percentages(self, service, collection):
        collection._results = [
            {
                "total": 10,
                "positive_count": 5,
                "neutral_count": 3,
                "negative_count": 2,
            }
        ]

        result = await service.get_sentiment_overview()

        assert result["total"] == 10
        assert result["positive_count"] == 5
        assert result["neutral_count"] == 3
        assert result["negative_count"] == 2
        assert result["positive_pct"] == 50.0
        assert result["neutral_pct"] == 30.0
        assert result["negative_pct"] == 20.0

    async def test_percentages_are_rounded_to_one_decimal(self, service, collection):
        collection._results = [
            {
                "total": 3,
                "positive_count": 1,
                "neutral_count": 1,
                "negative_count": 1,
            }
        ]

        result = await service.get_sentiment_overview()

        assert result["positive_pct"] == 33.3
        assert result["neutral_pct"] == 33.3
        assert result["negative_pct"] == 33.3

    async def test_only_positive_gives_100_percent(self, service, collection):
        collection._results = [
            {
                "total": 7,
                "positive_count": 7,
                "neutral_count": 0,
                "negative_count": 0,
            }
        ]

        result = await service.get_sentiment_overview()

        assert result["positive_pct"] == 100.0
        assert result["neutral_pct"] == 0.0
        assert result["negative_pct"] == 0.0

    async def test_zero_total_row_returns_zero_percentages(self, service, collection):
        collection._results = [
            {
                "total": 0,
                "positive_count": 0,
                "neutral_count": 0,
                "negative_count": 0,
            }
        ]

        result = await service.get_sentiment_overview()

        assert result["positive_pct"] == 0.0
        assert result["neutral_pct"] == 0.0
        assert result["negative_pct"] == 0.0

    async def test_pipeline_filters_deleted_and_groups_by_sentiment(self, service, collection):
        await service.get_sentiment_overview()

        assert len(collection.aggregate_calls) == 1
        pipeline = collection.aggregate_calls[0]
        assert pipeline[0] == {"$match": {"deleted_at": None}}
        group = pipeline[1]["$group"]
        assert group["total"] == {"$sum": 1}
        assert group["positive_count"]["$sum"]["$cond"][0] == {"$eq": ["$sentiment", "positive"]}
        assert group["neutral_count"]["$sum"]["$cond"][0] == {"$eq": ["$sentiment", "neutral"]}
        assert group["negative_count"]["$sum"]["$cond"][0] == {"$eq": ["$sentiment", "negative"]}

    async def test_result_contains_all_expected_keys(self, service, collection):
        collection._results = [
            {
                "total": 1,
                "positive_count": 1,
                "neutral_count": 0,
                "negative_count": 0,
            }
        ]

        result = await service.get_sentiment_overview()

        assert set(result.keys()) == {
            "total",
            "positive_count",
            "neutral_count",
            "negative_count",
            "positive_pct",
            "neutral_pct",
            "negative_pct",
        }
