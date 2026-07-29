from datetime import datetime, UTC
from typing import Dict
from pydantic import Field
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.domain.recommendation.entities.store_capabilities import StoreCapabilities


class StoreCapabilitiesDocument(BaseMongoDocument):
    store_id: str = Field(..., index=True, unique=True)
    capabilities: Dict[str, bool] = Field(default_factory=lambda: {"has_promo_codes": False})
    auto_detected: Dict[str, bool] = Field(default_factory=dict)

    def to_entity(self) -> StoreCapabilities:
        return StoreCapabilities(
            id=str(self.id),
            store_id=self.store_id,
            capabilities=self.capabilities,
            auto_detected=self.auto_detected,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: StoreCapabilities) -> "StoreCapabilitiesDocument":
        return cls(
            _id=entity.id,
            store_id=entity.store_id,
            capabilities=entity.capabilities,
            auto_detected=entity.auto_detected,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
