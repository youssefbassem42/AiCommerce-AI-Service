from typing import List, Optional, Any
from bson import ObjectId
import logging

from app.domain.analytics.entities.runtime_log import AIRuntimeLog
from app.domain.analytics.entities.prompt_history import PromptHistory
from app.domain.analytics.entities.dashboard_insight import DashboardInsight
from app.domain.analytics.repositories.analytics_repository import AnalyticsRepository as IAnalyticsRepository
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository
from app.infrastructure.mongodb.documents.runtime_log_document import AIRuntimeLogDocument
from app.infrastructure.mongodb.documents.prompt_history_document import PromptHistoryDocument
from app.infrastructure.mongodb.documents.dashboard_document import DashboardInsightDocument
from app.infrastructure.mongodb.collections import get_runtime_logs_collection, get_prompt_history_collection, get_dashboard_insights_collection

logger = logging.getLogger(__name__)

class AnalyticsRepository(BaseMongoRepository[AIRuntimeLogDocument, AIRuntimeLog], IAnalyticsRepository):
    """MongoDB implementation of the AnalyticsRepository with session and transaction support."""

    def __init__(self):
        super().__init__(get_runtime_logs_collection(), AIRuntimeLogDocument)
        self.prompt_collection = get_prompt_history_collection()
        self.insights_collection = get_dashboard_insights_collection()

    async def create(self, entity: AIRuntimeLog, session: Any = None) -> AIRuntimeLog:
        """Persist a runtime log along with any associated prompt histories atomically."""
        try:
            await super().create(entity, session=session)
            if entity.prompt_histories:
                prompt_docs = [PromptHistoryDocument.from_entity(ph).to_mongo_dict() for ph in entity.prompt_histories]
                await self.prompt_collection.insert_many(prompt_docs, session=session)
            return entity
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def find_by_id(self, id: str, session: Any = None) -> Optional[AIRuntimeLog]:
        """Find a runtime log by ID and populate its prompt histories."""
        try:
            log = await super().find_by_id(id, session=session)
            if not log:
                return None
            
            cursor = self.prompt_collection.find(
                {"runtimeId": id}, 
                session=session
            ).sort("timestamp", 1)
            
            histories = []
            async for data in cursor:
                doc = PromptHistoryDocument.from_mongo_dict(data)
                histories.append(doc.to_entity())
            log.prompt_histories = histories
            return log
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def get_logs_by_conversation(self, conversation_id: str, session: Any = None) -> List[AIRuntimeLog]:
        """Fetch all execution traces for a conversation."""
        try:
            logs = await self.find_many({"conversation_id": conversation_id}, session=session)
            for log in logs:
                cursor = self.prompt_collection.find(
                    {"runtimeId": log.id}, 
                    session=session
                ).sort("timestamp", 1)
                
                histories = []
                async for data in cursor:
                    doc = PromptHistoryDocument.from_mongo_dict(data)
                    histories.append(doc.to_entity())
                log.prompt_histories = histories
            return logs
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def get_dashboard_insights(
        self, store_id: str, metric_name: Optional[str] = None, session: Any = None
    ) -> List[DashboardInsight]:
        """Retrieve insights for the merchant dashboard."""
        try:
            filters = {"store_id": store_id}
            cursor = self.insights_collection.find(filters, session=session).sort("calculated_at", -1)
            insights = []
            async for data in cursor:
                doc = DashboardInsightDocument.from_mongo_dict(data)
                insights.append(doc.to_entity())
            return insights
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def save_dashboard_insight(self, insight: DashboardInsight, session: Any = None) -> DashboardInsight:
        """Create or update a calculated dashboard metric (unique on store_id)."""
        try:
            doc = DashboardInsightDocument.from_entity(insight)
            data = doc.to_mongo_dict()
            await self.insights_collection.replace_one(
                {"store_id": insight.store_id},
                data,
                upsert=True,
                session=session
            )
            return insight
        except Exception as e:
            self._handle_db_error(e)
            raise
