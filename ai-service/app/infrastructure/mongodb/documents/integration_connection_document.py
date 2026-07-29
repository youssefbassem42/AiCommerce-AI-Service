from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.domain.integration.entities.integration_connection import (
    ConnectionStatus,
    IntegrationConnection,
)
from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType, CredentialsLocation
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig, PaginationStyle
from app.domain.commerce.value_objects.audit import AuditInfo
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class AuthConfigModel(BaseModel):
    type: str = "apiKey"
    credentials_location: str = "header"
    scheme: Optional[str] = None
    name: Optional[str] = None
    token_url: Optional[str] = None
    flow: Optional[str] = None

    def to_vo(self) -> AuthConfig:
        return AuthConfig(
            type=AuthType(self.type),
            credentials_location=CredentialsLocation(self.credentials_location),
            scheme=self.scheme,
            name=self.name,
            token_url=self.token_url,
            flow=self.flow,
        )

    @classmethod
    def from_vo(cls, vo: AuthConfig) -> "AuthConfigModel":
        return cls(
            type=vo.type.value,
            credentials_location=vo.credentials_location.value,
            scheme=vo.scheme,
            name=vo.name,
            token_url=vo.token_url,
            flow=vo.flow,
        )


class FieldMappingModel(BaseModel):
    source: str
    target: str
    transformer: Optional[str] = None
    default_value: Any = None
    required: bool = False

    def to_vo(self) -> FieldMapping:
        return FieldMapping(
            source=self.source,
            target=self.target,
            transformer=self.transformer,
            default_value=self.default_value,
            required=self.required,
        )

    @classmethod
    def from_vo(cls, vo: FieldMapping) -> "FieldMappingModel":
        return cls(
            source=vo.source,
            target=vo.target,
            transformer=vo.transformer,
            default_value=vo.default_value,
            required=vo.required,
        )


class PaginationConfigModel(BaseModel):
    style: str = "none"
    page_param: Optional[str] = None
    limit_param: Optional[str] = None
    default_limit: int = 20
    cursor_field: Optional[str] = None
    total_field: Optional[str] = None
    next_link_field: Optional[str] = None

    def to_vo(self) -> PaginationConfig:
        return PaginationConfig(
            style=PaginationStyle(self.style),
            page_param=self.page_param,
            limit_param=self.limit_param,
            default_limit=self.default_limit,
            cursor_field=self.cursor_field,
            total_field=self.total_field,
            next_link_field=self.next_link_field,
        )

    @classmethod
    def from_vo(cls, vo: PaginationConfig) -> "PaginationConfigModel":
        return cls(
            style=vo.style.value,
            page_param=vo.page_param,
            limit_param=vo.limit_param,
            default_limit=vo.default_limit,
            cursor_field=vo.cursor_field,
            total_field=vo.total_field,
            next_link_field=vo.next_link_field,
        )


class EntityMappingModel(BaseModel):
    entity_type: str
    list_path: Optional[str] = None
    list_method: str = "GET"
    detail_path: Optional[str] = None
    detail_method: str = "GET"
    id_field: str
    pagination: PaginationConfigModel = Field(default_factory=PaginationConfigModel)
    field_mappings: list[FieldMappingModel] = Field(default_factory=list)

    def to_vo(self) -> EntityMapping:
        return EntityMapping(
            entity_type=self.entity_type,
            list_path=self.list_path,
            list_method=self.list_method,
            detail_path=self.detail_path,
            detail_method=self.detail_method,
            id_field=self.id_field,
            pagination=self.pagination.to_vo(),
            field_mappings=[fm.to_vo() for fm in self.field_mappings],
        )

    @classmethod
    def from_vo(cls, vo: EntityMapping) -> "EntityMappingModel":
        return cls(
            entity_type=vo.entity_type,
            list_path=vo.list_path,
            list_method=vo.list_method,
            detail_path=vo.detail_path,
            detail_method=vo.detail_method,
            id_field=vo.id_field,
            pagination=PaginationConfigModel.from_vo(vo.pagination),
            field_mappings=[FieldMappingModel.from_vo(fm) for fm in vo.field_mappings],
        )


class AuditInfoModel(BaseModel):
    created_at: Any
    updated_at: Any
    updated_by: Optional[str] = None

    def to_vo(self) -> AuditInfo:
        return AuditInfo(
            created_at=self.created_at,
            updated_at=self.updated_at,
            updated_by=self.updated_by,
        )

    @classmethod
    def from_vo(cls, vo: AuditInfo) -> "AuditInfoModel":
        return cls(
            created_at=vo.created_at,
            updated_at=vo.updated_at,
            updated_by=vo.updated_by,
        )


class IntegrationConnectionDocument(BaseMongoDocument):
    store_id: str = Field(..., min_length=1)
    organization_id: str = Field(...)
    name: str = Field(...)
    platform_name: str = Field(...)
    status: str = "inactive"
    spec_version: str = "3.0"
    raw_spec: dict = Field(default_factory=dict)
    auth_config: AuthConfigModel = Field(default_factory=AuthConfigModel)
    encrypted_credentials: Optional[str] = None
    entity_mappings: list[EntityMappingModel] = Field(default_factory=list)
    discovered_endpoints: list[dict] = Field(default_factory=list)
    discovered_schemas: dict = Field(default_factory=dict)
    last_sync_at: Any = None
    last_sync_status: Optional[str] = None
    error_message: Optional[str] = None
    audit: AuditInfoModel = Field(default_factory=AuditInfoModel)

    def to_entity(self) -> IntegrationConnection:
        return IntegrationConnection(
            id=str(self.id),
            store_id=self.store_id,
            organization_id=self.organization_id,
            name=self.name,
            platform_name=self.platform_name,
            status=ConnectionStatus(self.status),
            spec_version=self.spec_version,
            raw_spec=self.raw_spec,
            auth_config=self.auth_config.to_vo(),
            encrypted_credentials=self.encrypted_credentials,
            entity_mappings=[em.to_vo() for em in self.entity_mappings],
            discovered_endpoints=self.discovered_endpoints,
            discovered_schemas=self.discovered_schemas,
            last_sync_at=self.last_sync_at,
            last_sync_status=self.last_sync_status,
            error_message=self.error_message,
            audit=self.audit.to_vo(),
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: IntegrationConnection) -> "IntegrationConnectionDocument":
        kwargs = {
            "store_id": entity.store_id,
            "organization_id": entity.organization_id,
            "name": entity.name,
            "platform_name": entity.platform_name,
            "status": entity.status.value,
            "spec_version": entity.spec_version,
            "raw_spec": entity.raw_spec,
            "auth_config": AuthConfigModel.from_vo(entity.auth_config),
            "encrypted_credentials": entity.encrypted_credentials,
            "entity_mappings": [EntityMappingModel.from_vo(em) for em in entity.entity_mappings],
            "discovered_endpoints": entity.discovered_endpoints,
            "discovered_schemas": entity.discovered_schemas,
            "last_sync_at": entity.last_sync_at,
            "last_sync_status": entity.last_sync_status,
            "error_message": entity.error_message,
            "audit": AuditInfoModel.from_vo(entity.audit),
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
            "deleted_at": entity.deleted_at,
        }
        if entity.id:
            kwargs["_id"] = entity.id
        return cls(**kwargs)