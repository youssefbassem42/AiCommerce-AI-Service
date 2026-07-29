from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuthConfigSchema(BaseModel):
    type: str = "apiKey"
    credentials_location: str = "header"
    scheme: str | None = None
    name: str | None = None
    token_url: str | None = None
    flow: str | None = None


class PaginationConfigSchema(BaseModel):
    style: str = "none"
    page_param: str | None = None
    limit_param: str | None = None
    default_limit: int = 20
    cursor_field: str | None = None
    total_field: str | None = None
    next_link_field: str | None = None


class FieldMappingSchema(BaseModel):
    source: str
    target: str
    transformer: str | None = None
    default_value: Any = None
    required: bool = False


class EntityMappingSchema(BaseModel):
    entity_type: str
    list_path: str | None = None
    list_method: str = "GET"
    detail_path: str | None = None
    detail_method: str = "GET"
    id_field: str = "id"
    pagination: PaginationConfigSchema = Field(default_factory=PaginationConfigSchema)
    field_mappings: list[FieldMappingSchema] = Field(default_factory=list)


class EndpointSchema(BaseModel):
    path: str
    method: str
    operation_id: str | None = None
    summary: str | None = None
    parameters: list[dict] = Field(default_factory=list)
    response_schema_ref: str | None = None


class DiscoveredEntitySchema(BaseModel):
    entity_type: str
    confidence: float
    matched_fields: list[str]
    endpoint_path: str
    endpoint_method: str


class SuggestedMappingSchema(BaseModel):
    entity_type: str
    list_path: str | None = None
    id_field: str = "id"
    field_mappings: list[FieldMappingSchema] = Field(default_factory=list)


class ParseSpecRequestSchema(BaseModel):
    platform_name: str
    raw_spec: Any = Field(..., description="OpenAPI/Swagger specification (JSON dict, YAML string, or raw dict)")


class ParseSpecResponseSchema(BaseModel):
    platform_name: str
    base_url: str
    api_version: str
    endpoints: list[EndpointSchema]
    schemas: dict[str, Any]
    auth_methods: list[AuthConfigSchema]
    discovered_entities: list[DiscoveredEntitySchema] = Field(default_factory=list)
    suggested_mappings: list[SuggestedMappingSchema] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CreateConnectionSchema(BaseModel):
    store_id: str
    name: str
    platform_name: str
    raw_spec: Any = Field(..., description="OpenAPI/Swagger specification (JSON dict, YAML string, or raw dict)")
    auth_config: AuthConfigSchema
    credentials: dict[str, str] = Field(default_factory=dict)
    entity_mappings: list[EntityMappingSchema] = Field(default_factory=list)


class UpdateMappingsSchema(BaseModel):
    entity_mappings: list[EntityMappingSchema]


class UpdateCredentialsSchema(BaseModel):
    auth_config: AuthConfigSchema
    credentials: dict[str, str]


class ConnectionResponseSchema(BaseModel):
    id: str
    store_id: str
    organization_id: str
    name: str
    platform_name: str
    status: str
    spec_version: str
    auth_config: AuthConfigSchema
    entity_mappings: list[EntityMappingSchema]
    discovered_endpoints: list[dict] = Field(default_factory=list)
    discovered_schemas: dict = Field(default_factory=dict)
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_vector_sync_at: datetime | None = None
    last_vector_sync_status: str | None = None
    vector_sync_error: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedConnectionResponseSchema(BaseModel):
    items: list[ConnectionResponseSchema]
    total: int
    page: int
    page_size: int


class EntitySyncResultSchema(BaseModel):
    entity_type: str
    total_fetched: int = 0
    total_mapped: int = 0
    total_upserted: int = 0
    errors: list[str] = Field(default_factory=list)
    vector_sync: dict | None = None


class SyncRequestSchema(BaseModel):
    entity_types: list[str] | None = None


class SyncResponseSchema(BaseModel):
    connection_id: str
    store_id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    entity_results: list[EntitySyncResultSchema] = Field(default_factory=list)
    total_duration_seconds: float | None = None
    error: str | None = None


class DeleteResponseSchema(BaseModel):
    success: bool


class AgentParseRequestSchema(BaseModel):
    platform_name: str = Field(..., description="Name of the platform (e.g., Shopify, WooCommerce)")
    raw_spec: Any = Field(..., description="OpenAPI/Swagger specification (JSON object, YAML string, or raw dict)")


class UnsupportedFeatureSchema(BaseModel):
    feature_name: str
    description: str
    reason: str
    impact: str
    user_message: str


class FeatureAnalysisSchema(BaseModel):
    supported_features: list[str] = Field(default_factory=list)
    partially_supported: list[str] = Field(default_factory=list)
    unsupported_features: list[UnsupportedFeatureSchema] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AgentParseResponseSchema(BaseModel):
    platform_name: str
    base_url: str
    api_version: str
    entities: list[dict] = Field(default_factory=list, description="Discovered entities with field mappings")
    feature_analysis: FeatureAnalysisSchema = Field(default_factory=FeatureAnalysisSchema)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    user_friendly_error: str | None = None


class AgentSyncRequestSchema(BaseModel):
    platform_name: str = Field(..., description="Name of the platform")
    raw_spec: Any = Field(..., description="OpenAPI/Swagger specification")
    store_id: str = Field(..., description="Store ID for the integration")
    name: str | None = Field(default=None, description="Optional connection name")
    credentials: dict[str, str] | None = Field(default=None, description="API credentials (tokens, keys)")
    auto_sync: bool = Field(default=True, description="Run sync automatically after mapping")


class AgentSyncResponseSchema(BaseModel):
    connection_id: str | None = None
    mapping_report: dict | None = None
    capabilities: dict[str, bool] | None = None
    sync_result: dict | None = None
    feature_analysis: FeatureAnalysisSchema | None = None
    error: str | None = None
    user_friendly_error: str | None = None
    started_at: str
    completed_at: str | None = None
