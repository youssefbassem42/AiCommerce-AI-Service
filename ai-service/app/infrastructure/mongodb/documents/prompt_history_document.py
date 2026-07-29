from datetime import datetime, UTC
from typing import Dict, Any
from pydantic import Field
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.domain.analytics.entities.prompt_history import PromptHistory

class PromptHistoryDocument(BaseMongoDocument):
    """MongoDB document model representing PromptHistory."""
    runtimeId: str = Field(..., index=True)
    provider: str = Field(...)
    context: str = Field(...)
    model: str = Field(...)
    system_prompt: str = Field(...)
    user_prompt: str = Field(...)
    llm_response: str = Field(...)
    token_used: int = Field(...)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_entity(self) -> PromptHistory:
        """Map document to domain Entity."""
        return PromptHistory(
            id=str(self.id),
            runtimeId=self.runtimeId,
            provider=self.provider,
            context=self.context,
            model=self.model,
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt,
            llm_response=self.llm_response,
            token_used=self.token_used,
            timestamp=self.timestamp
        )

    @classmethod
    def from_entity(cls, entity: PromptHistory) -> "PromptHistoryDocument":
        """Map domain Entity to MongoDB Document."""
        return cls(
            _id=entity.id,
            runtimeId=entity.runtimeId,
            provider=entity.provider,
            context=entity.context,
            model=entity.model,
            system_prompt=entity.system_prompt,
            user_prompt=entity.user_prompt,
            llm_response=entity.llm_response,
            token_used=entity.token_used,
            timestamp=entity.timestamp
        )
