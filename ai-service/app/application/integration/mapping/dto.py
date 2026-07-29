from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.domain.integration.value_objects.auth_config import AuthConfig
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig


class AuthConfigDTO(BaseModel):
    type: str = "apiKey"
    credentials_location: str = "header"
    scheme: Optional[str] = None
    name: Optional[str] = None
    token_url: Optional[str] = None
    flow: Optional[str] = None


class PaginationConfigDTO(BaseModel):
    style: str = "none"
    page_param: Optional[str] = None
    limit_param: Optional[str] = None
    default_limit: int = 20
    cursor_field: Optional[str] = None
    total_field: Optional[str] = None
    next_link_field: Optional[str] = None


class FieldMappingDTO(BaseModel):
    source: str
    target: str
    transformer: Optional[str] = None
    default_value: Any = None
    required: bool = False


class EntityMappingDTO(BaseModel):
    entity_type: str
    list_path: Optional[str] = None
    list_method: str = "GET"
    detail_path: Optional[str] = None
    detail_method: str = "GET"
    id_field: str = "id"
    pagination: PaginationConfigDTO = Field(default_factory=PaginationConfigDTO)
    field_mappings: list[FieldMappingDTO] = Field(default_factory=list)


class EndpointSchemaDTO(BaseModel):
    path: str
    method: str
    operation_id: Optional[str] = None
    summary: Optional[str] = None
    parameters: list[dict] = Field(default_factory=list)
    response_schema_ref: Optional[str] = None


class ParsedSpecDTO(BaseModel):
    platform_name: str
    base_url: str
    api_version: str
    endpoints: list[EndpointSchemaDTO] = Field(default_factory=list)
    schemas: dict[str, Any] = Field(default_factory=dict)
    auth_methods: list[AuthConfigDTO] = Field(default_factory=list)


class ConnectionResponseDTO(BaseModel):
    id: str
    store_id: str
    organization_id: str
    name: str
    platform_name: str
    status: str
    spec_version: str
    auth_config: AuthConfigDTO
    entity_mappings: list[EntityMappingDTO] = Field(default_factory=list)
    discovered_endpoints: list[dict] = Field(default_factory=list)
    discovered_schemas: dict = Field(default_factory=dict)
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ConnectionCreateDTO(BaseModel):
    store_id: str
    organization_id: str
    name: str
    platform_name: str
    raw_spec: dict
    auth_config: AuthConfigDTO
    credentials: dict[str, str] = Field(default_factory=dict)
    entity_mappings: list[EntityMappingDTO] = Field(default_factory=list)


class ConnectionUpdateMappingsDTO(BaseModel):
    entity_mappings: list[EntityMappingDTO]


class ConnectionUpdateCredentialsDTO(BaseModel):
    auth_config: AuthConfigDTO
    credentials: dict[str, str]


class ParseSpecRequestDTO(BaseModel):
    platform_name: str
    raw_spec: dict


class ParseSpecResponseDTO(BaseModel):
    platform_name: str
    base_url: str
    api_version: str
    endpoints: list[EndpointSchemaDTO]
    schemas: dict[str, Any]
    auth_methods: list[AuthConfigDTO]
    discovered_entities: list[dict] = Field(default_factory=list)
    suggested_mappings: list[EntityMappingDTO] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)