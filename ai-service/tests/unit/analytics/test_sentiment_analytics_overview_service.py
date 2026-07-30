from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService


@pytest.fixture
def mock_cursor():
    cursor = AsyncMock()
    cursor.to_list = AsyncMock()
    return cursor


@pytest.fixture
def mock_collection(mock_cursor):
    coll = MagicMock()
    coll.aggregate.return_value = mock_cursor
    return coll


@pytest.fixture
def service():
    return SentimentAnalyticsService()


class TestSentimentOverview:
    async def test_returns_breakdown_from_aggregation(self, service, mock_collection, mock_cursor):
        mock_cursor.to_list.return_value = [
            {
                "_id": None,
                "total": 100,
                "positive_count": 50,
                "neutral_count": 30,
                "negative_count": 20,
            }
        ]
        with patch(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            return_value=mock_collection,
        ):
            result = await service.get_sentiment_overview()

        assert result == {
            "total": 100,
            "positive_count": 50,
            "neutral_count": 30,
            "negative_count": 20,
            "positive_pct": 50.0,
            "neutral_pct": 30.0,
            "negative_pct": 20.0,
        }
        mock_collection.aggregate.assert_called_once()

    async def test_no_tickets_returns_zeros(self, service, mock_collection, mock_cursor):
        mock_cursor.to_list.return_value = []
        with patch(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            return_value=mock_collection,
        ):
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

    async def test_all_positive(self, service, mock_collection, mock_cursor):
        mock_cursor.to_list.return_value = [
            {"_id": None, "total": 5, "positive_count": 5, "neutral_count": 0, "negative_count": 0}
        ]
        with patch(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            return_value=mock_collection,
        ):
            result = await service.get_sentiment_overview()

        assert result["positive_pct"] == 100.0
        assert result["neutral_pct"] == 0.0
        assert result["negative_pct"] == 0.0

    async def test_all_negative(self, service, mock_collection, mock_cursor):
        mock_cursor.to_list.return_value = [
            {"_id": None, "total": 3, "positive_count": 0, "neutral_count": 0, "negative_count": 3}
        ]
        with patch(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            return_value=mock_collection,
        ):
            result = await service.get_sentiment_overview()

        assert result["negative_pct"] == 100.0
        assert result["positive_pct"] == 0.0
        assert result["neutral_pct"] == 0.0

    async def test_mixed_sentiments_correct_percentages(self, service, mock_collection, mock_cursor):
        mock_cursor.to_list.return_value = [
            {"_id": None, "total": 6, "positive_count": 2, "neutral_count": 3, "negative_count": 1}
        ]
        with patch(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            return_value=mock_collection,
        ):
            result = await service.get_sentiment_overview()

        assert result["positive_pct"] == 33.3
        assert result["neutral_pct"] == 50.0
        assert result["negative_pct"] == 16.7

    async def test_rounding_precision(self, service, mock_collection, mock_cursor):
        mock_cursor.to_list.return_value = [
            {"_id": None, "total": 3, "positive_count": 1, "neutral_count": 1, "negative_count": 1}
        ]
        with patch(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            return_value=mock_collection,
        ):
            result = await service.get_sentiment_overview()

        assert result["positive_pct"] == 33.3
        assert result["neutral_pct"] == 33.3
        assert result["negative_pct"] == 33.3

    async def test_pipeline_includes_deleted_at_filter(self, service, mock_collection, mock_cursor):
        mock_cursor.to_list.return_value = []
        with patch(
            "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
            return_value=mock_collection,
        ):
            await service.get_sentiment_overview()

        pipeline = mock_collection.aggregate.call_args[0][0]
        assert pipeline[0]["$match"] == {"deleted_at": None}
