from datetime import datetime, UTC
from typing import List, Dict, Any, Optional
from pydantic import Field
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.infrastructure.mongodb.documents.prompt_history_document import PromptHistoryDocument
from app.domain.analytics.entities.runtime_log import AIRuntimeLog

class AIRuntimeLogDocument(BaseMongoDocument):
    """MongoDB document model representing AIRuntimeLog."""
    conversation_id: str = Field(..., index=True)
    model: str = Field(...)
    prompt_tokens: str = Field(...)
    latency: float = Field(...)
    level: str = Field(default="INFO")
    message: str = Field(...)
    details: Dict[str, Any] = Field(default_factory=dict)
    prompt_histories: Optional[List[PromptHistoryDocument]] = Field(default=None, exclude=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

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
            timestamp=self.timestamp
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
            prompt_histories=[PromptHistoryDocument.from_entity(ph) for ph in entity.prompt_histories] if entity.prompt_histories else [],
            timestamp=entity.timestamp
        )
