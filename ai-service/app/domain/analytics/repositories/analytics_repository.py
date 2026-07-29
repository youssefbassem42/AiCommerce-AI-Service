from abc import ABC, abstractmethod
from typing import List, Optional
from app.shared.kernel.repository import AsyncRepository
from app.domain.analytics.entities.runtime_log import AIRuntimeLog
from app.domain.analytics.entities.dashboard_insight import DashboardInsight

class AnalyticsRepository(AsyncRepository[AIRuntimeLog, str], ABC):
    """Domain repository interface for Analytics & Logging Context."""

    @abstractmethod
    async def get_logs_by_conversation(self, conversation_id: str) -> List[AIRuntimeLog]:
        """Fetch all execution traces for a conversation."""
        pass

    @abstractmethod
    async def get_dashboard_insights(self, store_id: str, metric_name: Optional[str] = None) -> List[DashboardInsight]:
        """Retrieve insights for the merchant dashboard."""
        pass

    @abstractmethod
    async def save_dashboard_insight(self, insight: DashboardInsight) -> DashboardInsight:
        """Create or update a calculated dashboard metric."""
        pass
