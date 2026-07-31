import pytest

from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService


class RaisingCursor:
    async def to_list(self, length):
        raise RuntimeError("aggregate failed")


class RaisingCollection:
    def aggregate(self, pipeline):
        return RaisingCursor()


class EmptyCursor:
    async def to_list(self, length):
        return []


class EmptyCollection:
    def aggregate(self, pipeline):
        return EmptyCursor()


class TestSentimentAnalyticsService:
    @pytest.fixture
    def service(self):
        return SentimentAnalyticsService()

    async def test_aggregate_failure_propagates(self, service, monkeypatch):
        monkeypatch.setattr(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            lambda: RaisingCollection(),
        )

        with pytest.raises(RuntimeError, match="aggregate failed"):
            await service.get_sentiment_overview()

    async def test_empty_aggregate_result(self, service, monkeypatch):
        monkeypatch.setattr(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            lambda: EmptyCollection(),
        )

        result = await service.get_sentiment_overview()

        assert result["total"] == 0

    async def test_single_row_with_all_zeros(self, service, monkeypatch):
        class Collection:
            def aggregate(self, pipeline):
                class Cursor:
                    async def to_list(self, length):
                        return [
                            {
                                "total": 0,
                                "positive_count": 0,
                                "neutral_count": 0,
                                "negative_count": 0,
                            }
                        ]

                return Cursor()

        monkeypatch.setattr(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            lambda: Collection(),
        )

        result = await service.get_sentiment_overview()

        assert result["positive_pct"] == 0.0
        assert result["neutral_pct"] == 0.0
        assert result["negative_pct"] == 0.0

    async def test_partial_sentiment_counts(self, service, monkeypatch):
        class Collection:
            def aggregate(self, pipeline):
                class Cursor:
                    async def to_list(self, length):
                        return [
                            {
                                "total": 4,
                                "positive_count": 2,
                                "neutral_count": 0,
                                "negative_count": 2,
                            }
                        ]

                return Cursor()

        monkeypatch.setattr(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            lambda: Collection(),
        )

        result = await service.get_sentiment_overview()

        assert result["positive_pct"] == 50.0
        assert result["neutral_pct"] == 0.0
        assert result["negative_pct"] == 50.0

    async def test_counts_are_ints_and_percentages_floats(self, service, monkeypatch):
        class Collection:
            def aggregate(self, pipeline):
                class Cursor:
                    async def to_list(self, length):
                        return [
                            {
                                "total": 100,
                                "positive_count": 25,
                                "neutral_count": 25,
                                "negative_count": 50,
                            }
                        ]

                return Cursor()

        monkeypatch.setattr(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            lambda: Collection(),
        )

        result = await service.get_sentiment_overview()

        assert isinstance(result["total"], int)
        assert isinstance(result["positive_count"], int)
        assert isinstance(result["positive_pct"], float)
