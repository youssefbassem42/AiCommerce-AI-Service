from pydantic import Field

from app.domain.widget.entities.widget_installation import (
    WIDGET_DEFAULT_SCOPES,
    WidgetInstallation,
)
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class WidgetInstallationDocument(BaseMongoDocument):
    widget_id: str = Field(..., index=True, unique=True)
    store_id: str = Field(..., index=True)
    organization_id: str = Field(...)
    public_key_hash: str = Field(..., index=True, unique=True)
    environment: str = Field(default="live")
    status: str = Field(default="active", index=True)
    allowed_origins: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=lambda: list(WIDGET_DEFAULT_SCOPES))
    last_used_at: object | None = None

    def to_entity(self) -> WidgetInstallation:
        return WidgetInstallation(
            id=str(self.id),
            widget_id=self.widget_id,
            store_id=self.store_id,
            organization_id=self.organization_id,
            public_key_hash=self.public_key_hash,
            environment=self.environment,
            status=self.status,
            allowed_origins=self.allowed_origins,
            scopes=self.scopes,
            last_used_at=self.last_used_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: WidgetInstallation) -> "WidgetInstallationDocument":
        return cls(
            _id=entity.id,
            widget_id=entity.widget_id,
            store_id=entity.store_id,
            organization_id=entity.organization_id,
            public_key_hash=entity.public_key_hash,
            environment=entity.environment,
            status=entity.status,
            allowed_origins=entity.allowed_origins,
            scopes=entity.scopes,
            last_used_at=entity.last_used_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
