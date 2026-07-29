from typing import Any, Optional
from pydantic import BaseModel, Field


class AuthInfo(BaseModel):
    type: str = "apiKey"
    credentials_location: str = "header"
    name: Optional[str] = None
    scheme: Optional[str] = None
    token_url: Optional[str] = None
    flow: Optional[str] = None


class PaginationInfo(BaseModel):
    style: str = "none"
    page_param: Optional[str] = None
    limit_param: Optional[str] = None
    default_limit: int = 20
    cursor_field: Optional[str] = None
    total_field: Optional[str] = None
    next_link_field: Optional[str] = None


class FieldMappingInfo(BaseModel):
    source: str = Field(..., description="Source field name in the external API response")
    target: str = Field(..., description="Target canonical field name")
    transformer: Optional[str] = Field(default=None, description="Transformer hint: string_to_decimal, iso_date, lowercase, etc.")
    required: bool = False
    default_value: Any = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    description: Optional[str] = Field(default=None, description="Why this mapping was chosen")


class DiscoveredEntityInfo(BaseModel):
    entity_type: str = Field(..., description="Canonical entity type name (e.g., product, order, customer, coupon)")
    display_name: str = Field(..., description="Human-readable name like 'Products', 'Customer Orders'")
    description: str = Field(..., description="What this entity represents in the external system")
    list_path: Optional[str] = Field(default=None, description="Path for listing records, e.g., /products")
    list_method: str = "GET"
    detail_path: Optional[str] = Field(default=None, description="Path for single record, e.g., /products/{id}")
    detail_method: str = "GET"
    create_path: Optional[str] = None
    create_method: Optional[str] = None
    update_path: Optional[str] = None
    update_method: Optional[str] = None
    delete_path: Optional[str] = None
    delete_method: Optional[str] = None
    id_field: str = "id"
    pagination: PaginationInfo = Field(default_factory=PaginationInfo)
    field_mappings: list[FieldMappingInfo] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class UnsupportedFeature(BaseModel):
    feature_name: str = Field(..., description="Name of the unsupported feature")
    description: str = Field(..., description="What this feature does")
    reason: str = Field(..., description="Why it won't work (specific endpoint/schema missing)")
    impact: str = Field(..., description="Business impact of this missing feature")
    user_message: str = Field(..., description="User-friendly message explaining the limitation to a non-technical user")


class FeatureAnalysis(BaseModel):
    supported_features: list[str] = Field(default_factory=list, description="E-commerce features fully supported by this API")
    partially_supported: list[str] = Field(default_factory=list, description="Features that work with limitations")
    unsupported_features: list[UnsupportedFeature] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, description="Additional observations about the platform capabilities")


class IntegrationMappingReport(BaseModel):
    platform_name: str
    base_url: str
    api_version: str
    spec_format: str = "json"
    entities: list[DiscoveredEntityInfo] = Field(default_factory=list)
    auth: Optional[AuthInfo] = None
    feature_analysis: FeatureAnalysis = Field(default_factory=FeatureAnalysis)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_unsupported_features(self) -> bool:
        return len(self.feature_analysis.unsupported_features) > 0
