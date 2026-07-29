from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field, model_validator

from app.domain.commerce.value_objects.audit import AuditInfo
from app.domain.integration.exceptions import IntegrationValidationException
from app.domain.integration.value_objects.auth_config import AuthConfig
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.shared.kernel.aggregate_root import AggregateRoot


class ConnectionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class IntegrationConnection(AggregateRoot[str]):
    """Aggregate root for an external e-commerce platform integration connection.

    Encapsulates the parsed spec, user-configured entity/field mappings,
    encrypted credentials, and sync status.  Credentials are stored as opaque
    ciphertext — decryption happens only when the HTTP client is constructed.
    """

    store_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=256)
    platform_name: str = Field(..., min_length=1, max_length=128)
    status: ConnectionStatus = ConnectionStatus.INACTIVE
    spec_version: str = "3.0"
    raw_spec: dict = Field(default_factory=dict)
    auth_config: AuthConfig = Field(default_factory=lambda: AuthConfig(type="apiKey", name="X-API-Key"))
    encrypted_credentials: Optional[str] = None
    entity_mappings: list[EntityMapping] = Field(default_factory=list)
    discovered_endpoints: list[dict] = Field(default_factory=list)
    discovered_schemas: dict = Field(default_factory=dict)
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_vector_sync_at: Optional[datetime] = None
    last_vector_sync_status: Optional[str] = None
    vector_sync_error: Optional[str] = None
    error_message: Optional[str] = None
    audit: AuditInfo = Field(default_factory=AuditInfo)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_name(self) -> "IntegrationConnection":
        if not self.name.strip():
            raise IntegrationValidationException("Connection name must not be empty.")
        return self

    def update_spec(
        self,
        version: str,
        raw_spec: dict,
        endpoints: list[dict],
        schemas: dict,
    ) -> None:
        self.spec_version = version
        self.raw_spec = raw_spec
        self.discovered_endpoints = endpoints
        self.discovered_schemas = schemas
        self.updated_at = datetime.now(UTC)

    def set_credentials(self, auth_config: AuthConfig, encrypted_value: str) -> None:
        self.auth_config = auth_config
        self.encrypted_credentials = encrypted_value
        self.updated_at = datetime.now(UTC)

    def replace_entity_mapping(self, mapping: EntityMapping) -> None:
        existing_index = None
        for i, em in enumerate(self.entity_mappings):
            if em.entity_type == mapping.entity_type:
                existing_index = i
                break
        if existing_index is not None:
            self.entity_mappings[existing_index] = mapping
        else:
            self.entity_mappings.append(mapping)
        self.updated_at = datetime.now(UTC)

    def remove_entity_mapping(self, entity_type: str) -> None:
        before = len(self.entity_mappings)
        self.entity_mappings = [
            em for em in self.entity_mappings if em.entity_type != entity_type
        ]
        if len(self.entity_mappings) == before:
            raise IntegrationValidationException(
                f"No entity mapping found for '{entity_type}'."
            )
        self.updated_at = datetime.now(UTC)

    def update_mappings(self, mappings: list[EntityMapping]) -> None:
        self.entity_mappings = mappings
        self.updated_at = datetime.now(UTC)

    def mark_synced(self, status: Optional[str] = None) -> None:
        if self.status == ConnectionStatus.INACTIVE:
            raise IntegrationValidationException("Cannot mark a sync on an inactive connection.")
        self.last_sync_at = datetime.now(UTC)
        self.last_sync_status = status or "success"
        self.error_message = None
        self.updated_at = datetime.now(UTC)

    def mark_vector_synced(self, status: Optional[str] = None) -> None:
        if self.status == ConnectionStatus.INACTIVE:
            raise IntegrationValidationException("Cannot mark vector sync on an inactive connection.")
        self.last_vector_sync_at = datetime.now(UTC)
        self.last_vector_sync_status = status or "success"
        self.vector_sync_error = None
        self.updated_at = datetime.now(UTC)

    def mark_vector_sync_error(self, message: str) -> None:
        self.last_vector_sync_at = datetime.now(UTC)
        self.last_vector_sync_status = "error"
        self.vector_sync_error = message
        self.updated_at = datetime.now(UTC)

    def mark_error(self, message: str) -> None:
        if self.status == ConnectionStatus.INACTIVE:
            raise IntegrationValidationException("Cannot mark error on an inactive connection.")
        self.status = ConnectionStatus.ERROR
        self.error_message = message
        self.updated_at = datetime.now(UTC)

    def activate(self) -> None:
        if self.status == ConnectionStatus.ACTIVE:
            return
        if not self.auth_config or not self.encrypted_credentials:
            raise IntegrationValidationException("Cannot activate without credentials.")
        self.status = ConnectionStatus.ACTIVE
        self.error_message = None
        self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        self.status = ConnectionStatus.INACTIVE
        self.updated_at = datetime.now(UTC)