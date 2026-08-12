from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.domain.analytics.entities.runtime_log import AIRuntimeLog
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.infrastructure.mongodb.documents.prompt_history_document import PromptHistoryDocument


class AIRuntimeLogDocument(BaseMongoDocument):
    """MongoDB document model representing AIRuntimeLog."""

    conversation_id: str = Field(..., index=True)
    model: str = Field(...)
    prompt_tokens: str = Field(...)
    latency: float = Field(...)
    level: str = Field(default="INFO")
    message: str = Field(...)
    details: dict[str, Any] = Field(default_factory=dict)
    prompt_histories: list[PromptHistoryDocument] | None = Field(default=None, exclude=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    store_id: str = Field(default="")
    organization_id: str = Field(default="")
    billing_period: str = Field(default="")
    provider: str = Field(default="")
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    cost: float = Field(default=0.0)
    session_id: str = Field(default="")

    def to_entity(self) -> AIRuntimeLog:
        """Map document to domain Entity."""
        return AIRuntimeLog(
            id=str(self.id),
            conversation_id=self.conversation_id,
            model=self.model,
            prompt_tokens=self.prompt_tokens,
            latency=self.latency,
            level=self.level,
            message=self.message,
            details=self.details,
            prompt_histories=[ph.to_entity() for ph in self.prompt_histories] if self.prompt_histories else [],
            timestamp=self.timestamp,
            store_id=self.store_id,
            organization_id=self.organization_id,
            billing_period=self.billing_period,
            provider=self.provider,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
            cost=self.cost,
            session_id=self.session_id,
        )

    @classmethod
    def from_entity(cls, entity: AIRuntimeLog) -> "AIRuntimeLogDocument":
        """Map domain Entity to MongoDB Document."""
        return cls(
            _id=entity.id,
            conversation_id=entity.conversation_id,
            model=entity.model,
            prompt_tokens=entity.prompt_tokens,
            latency=entity.latency,
            level=entity.level,
            message=entity.message,
            details=entity.details,
            prompt_histories=[PromptHistoryDocument.from_entity(ph) for ph in entity.prompt_histories]
            if entity.prompt_histories
            else [],
            timestamp=entity.timestamp,
            store_id=entity.store_id,
            organization_id=entity.organization_id,
            billing_period=entity.billing_period,
            provider=entity.provider,
            completion_tokens=entity.completion_tokens,
            total_tokens=entity.total_tokens,
            cost=entity.cost,
            session_id=entity.session_id,
        )
