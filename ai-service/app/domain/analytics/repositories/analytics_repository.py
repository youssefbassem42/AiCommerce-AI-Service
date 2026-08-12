from abc import ABC, abstractmethod

from app.domain.analytics.entities.dashboard_insight import DashboardInsight
from app.domain.analytics.entities.runtime_log import AIRuntimeLog
from app.shared.kernel.repository import AsyncRepository


class AnalyticsRepository(AsyncRepository[AIRuntimeLog, str], ABC):
    """Domain repository interface for Analytics & Logging Context."""

    @abstractmethod
    async def get_logs_by_conversation(self, conversation_id: str) -> list[AIRuntimeLog]:
        """Fetch all execution traces for a conversation."""
        pass

    @abstractmethod
    async def get_dashboard_insights(self, store_id: str, metric_name: str | None = None) -> list[DashboardInsight]:
        """Retrieve insights for the merchant dashboard."""
        pass

    @abstractmethod
    async def save_dashboard_insight(self, insight: DashboardInsight) -> DashboardInsight:
        """Create or update a calculated dashboard metric."""
        pass

    @abstractmethod
    async def aggregate_usage(self, store_id: str, billing_period: str) -> dict:
        """Aggregate token usage for the store within the billing period.

        Returns totals plus provider and model breakdowns (spec §21, §38-39).
        """
        pass
