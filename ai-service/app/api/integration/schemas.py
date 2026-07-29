from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuthConfigSchema(BaseModel):
    type: str = "apiKey"
    credentials_location: str = "header"
    scheme: Optional[str] = None
    name: Optional[str] = None
    token_url: Optional[str] = None
    flow: Optional[str] = None


class PaginationConfigSchema(BaseModel):
    style: str = "none"
    page_param: Optional[str] = None
    limit_param: Optional[str] = None
    default_limit: int = 20
    cursor_field: Optional[str] = None
    total_field: Optional[str] = None
    next_link_field: Optional[str] = None


class FieldMappingSchema(BaseModel):
    source: str
    target: str
    transformer: Optional[str] = None
    default_value: Any = None
    required: bool = False


class EntityMappingSchema(BaseModel):
    entity_type: str
    list_path: Optional[str] = None
    list_method: str = "GET"
    detail_path: Optional[str] = None
    detail_method: str = "GET"
    id_field: str = "id"
    pagination: PaginationConfigSchema = Field(default_factory=PaginationConfigSchema)
    field_mappings: list[FieldMappingSchema] = Field(default_factory=list)


class EndpointSchema(BaseModel):
    path: str
    method: str
    operation_id: Optional[str] = None
    summary: Optional[str] = None
    parameters: list[dict] = Field(default_factory=list)
    response_schema_ref: Optional[str] = None


class DiscoveredEntitySchema(BaseModel):
    entity_type: str
    confidence: float
    matched_fields: list[str]
    endpoint_path: str
    endpoint_method: str


class SuggestedMappingSchema(BaseModel):
    entity_type: str
    list_path: Optional[str] = None
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
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_vector_sync_at: Optional[datetime] = None
    last_vector_sync_status: Optional[str] = None
    vector_sync_error: Optional[str] = None
    error_message: Optional[str] = None
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
    vector_sync: Optional[dict] = None


class SyncRequestSchema(BaseModel):
    entity_types: Optional[list[str]] = None


class SyncResponseSchema(BaseModel):
    connection_id: str
    store_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    entity_results: list[EntitySyncResultSchema] = Field(default_factory=list)
    total_duration_seconds: Optional[float] = None
    error: Optional[str] = None


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
    user_friendly_error: Optional[str] = None


class AgentSyncRequestSchema(BaseModel):
    platform_name: str = Field(..., description="Name of the platform")
    raw_spec: Any = Field(..., description="OpenAPI/Swagger specification")
    store_id: str = Field(..., description="Store ID for the integration")
    name: Optional[str] = Field(default=None, description="Optional connection name")
    credentials: Optional[dict[str, str]] = Field(default=None, description="API credentials (tokens, keys)")
    auto_sync: bool = Field(default=True, description="Run sync automatically after mapping")


class AgentSyncResponseSchema(BaseModel):
    connection_id: Optional[str] = None
    mapping_report: Optional[dict] = None
    capabilities: Optional[dict[str, bool]] = None
    sync_result: Optional[dict] = None
    feature_analysis: Optional[FeatureAnalysisSchema] = None
    error: Optional[str] = None
    user_friendly_error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
