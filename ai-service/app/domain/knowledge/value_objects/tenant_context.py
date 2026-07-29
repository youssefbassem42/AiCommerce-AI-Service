from pydantic import BaseModel, Field, ConfigDict


class TenantContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: str = Field(..., description="Organization that owns the store")
    store_id: str = Field(..., description="Store the operation belongs to")
    merchant_id: str = Field(default="", description="Merchant running the store")
    integration_id: str = Field(default="", description="Active store integration ID")
    store_slug: str = Field(default="", description="Human-readable store slug")
    language: str = Field(default="en", description="Store default language")
    currency: str = Field(default="USD", description="Store default currency")
    timezone: str = Field(default="UTC", description="Store timezone")
    knowledge_version: int = Field(default=1, ge=1, description="Current knowledge base version")
    vector_namespace: str = Field(default="", description="Qdrant collection namespace for tenant isolation")

    def scope_filter(self) -> dict[str, str]:
        return {
            "organization_id": self.organization_id,
            "store_id": self.store_id,
        }

    @property
    def collection_name(self) -> str:
        suffix = self.vector_namespace or self.store_id
        return f"kb_{suffix}"
