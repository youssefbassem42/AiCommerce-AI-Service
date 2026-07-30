from unittest.mock import AsyncMock

import pytest

from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService
from app.domain.ticket.entities.ticket_analysis import TicketAnalysis


def make_ticket(store_id: str, sentiment: str) -> TicketAnalysis:
    return TicketAnalysis(
        id=f"tkt-{sentiment}",
        ticket_id=f"tkt-{sentiment}",
        store_id=store_id,
        customer_id="c1",
        sentiment=sentiment,
        category="general",
        summary="test",
        priority="low",
        status="open",
        suggested_response="ok",
    )


@pytest.fixture
def ticket_repo():
    repo = AsyncMock()
    repo.find_many = AsyncMock()
    return repo


@pytest.fixture
def service(ticket_repo):
    return SentimentAnalyticsService(ticket_repository=ticket_repo)


class TestSentimentAnalyticsService:
    async def test_all_sentiments_are_counted(self, service, ticket_repo):
        ticket_repo.find_many.return_value = [
            make_ticket("s1", "positive"),
            make_ticket("s1", "neutral"),
            make_ticket("s1", "negative"),
        ]
        result = await service.get_sentiment_summary("s1")
        assert result.total == 3
        assert result.positive_count == 1
        assert result.neutral_count == 1
        assert result.negative_count == 1
        assert result.positive_pct == 33.3
        assert result.neutral_pct == 33.3
        assert result.negative_pct == 33.3

    async def test_all_positive(self, service, ticket_repo):
        ticket_repo.find_many.return_value = [
            make_ticket("s1", "positive") for _ in range(4)
        ]
        result = await service.get_sentiment_summary("s1")
        assert result.total == 4
        assert result.positive_count == 4
        assert result.neutral_count == 0
        assert result.negative_count == 0
        assert result.positive_pct == 100.0
        assert result.neutral_pct == 0.0
        assert result.negative_pct == 0.0

    async def test_no_tickets_returns_zeros(self, service, ticket_repo):
        ticket_repo.find_many.return_value = []
        result = await service.get_sentiment_summary("s1")
        assert result.total == 0
        assert result.positive_count == 0
        assert result.neutral_count == 0
        assert result.negative_count == 0
        assert result.positive_pct == 0.0
        assert result.neutral_pct == 0.0
        assert result.negative_pct == 0.0

    async def test_uses_correct_store_id(self, service, ticket_repo):
        ticket_repo.find_many.return_value = []
        await service.get_sentiment_summary("store_abc")
        ticket_repo.find_many.assert_called_once_with({"store_id": "store_abc"})

    async def test_mixed_sentiments_correct_percentages(self, service, ticket_repo):
        ticket_repo.find_many.return_value = [
            make_ticket("s1", "positive"),
            make_ticket("s1", "positive"),
            make_ticket("s1", "neutral"),
            make_ticket("s1", "neutral"),
            make_ticket("s1", "neutral"),
            make_ticket("s1", "negative"),
        ]
        result = await service.get_sentiment_summary("s1")
        assert result.total == 6
        assert result.positive_count == 2
        assert result.neutral_count == 3
        assert result.negative_count == 1
        assert result.positive_pct == 33.3
        assert result.neutral_pct == 50.0
        assert result.negative_pct == 16.7

    async def test_rounding_precision(self, service, ticket_repo):
        ticket_repo.find_many.return_value = [
            make_ticket("s1", "positive") for _ in range(1)
        ] + [make_ticket("s1", "neutral") for _ in range(3)]
        result = await service.get_sentiment_summary("s1")
        assert result.total == 4
        assert result.positive_pct == 25.0
        assert result.neutral_pct == 75.0
        assert result.negative_pct == 0.0
