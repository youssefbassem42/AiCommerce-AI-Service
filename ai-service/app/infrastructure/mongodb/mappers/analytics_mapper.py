from app.domain.analytics.entities.runtime_log import AIRuntimeLog
from app.domain.analytics.entities.prompt_history import PromptHistory
from app.domain.analytics.entities.dashboard_insight import DashboardInsight
from app.infrastructure.mongodb.documents.runtime_log_document import AIRuntimeLogDocument
from app.infrastructure.mongodb.documents.prompt_history_document import PromptHistoryDocument
from app.infrastructure.mongodb.documents.dashboard_document import DashboardInsightDocument
from app.application.analytics.dto.analytics_dto import AIRuntimeLogDTO, PromptHistoryDTO, DashboardInsightDTO

class AnalyticsMapper:
    """Maps Analytics & Logging aggregates between Mongo Documents, Domain Entities, and DTOs."""

    @staticmethod
    def to_entity(doc: AIRuntimeLogDocument) -> AIRuntimeLog:
        """Map Mongo Document to Domain Entity."""
        return doc.to_entity()

    @staticmethod
    def to_document(entity: AIRuntimeLog) -> AIRuntimeLogDocument:
        """Map Domain Entity to Mongo Document."""
        return AIRuntimeLogDocument.from_entity(entity)

    @staticmethod
    def to_dto(entity: AIRuntimeLog) -> AIRuntimeLogDTO:
        """Map Domain Entity to DTO."""
        return AIRuntimeLogDTO(
            id=entity.id,
            conversation_id=entity.conversation_id,
            model=entity.model,
            prompt_tokens=entity.prompt_tokens,
            latency=entity.latency,
            level=entity.level,
            message=entity.message,
            details=entity.details,
            prompt_histories=[
                PromptHistoryDTO(
                    id=ph.id,
                    runtimeId=ph.runtimeId,
                    provider=ph.provider,
                    context=ph.context,
                    model=ph.model,
                    system_prompt=ph.system_prompt,
                    user_prompt=ph.user_prompt,
                    llm_response=ph.llm_response,
                    token_used=ph.token_used,
                    timestamp=ph.timestamp
                )
                for ph in entity.prompt_histories
            ],
            timestamp=entity.timestamp
        )

    @staticmethod
    def insight_to_entity(doc: DashboardInsightDocument) -> DashboardInsight:
        """Map DashboardInsight Document to Domain Entity."""
        return doc.to_entity()

    @staticmethod
    def insight_to_document(entity: DashboardInsight) -> DashboardInsightDocument:
        """Map DashboardInsight Domain Entity to Mongo Document."""
        return DashboardInsightDocument.from_entity(entity)

    @staticmethod
    def insight_to_dto(entity: DashboardInsight) -> DashboardInsightDTO:
        """Map DashboardInsight Domain Entity to DTO."""
        return DashboardInsightDTO(
            id=entity.id,
            store_id=entity.store_id,
            recommendations=entity.recommendations,
            metadata=entity.metadata,
            calculated_at=entity.calculated_at
        )
