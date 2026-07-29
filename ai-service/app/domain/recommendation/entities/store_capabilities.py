from datetime import UTC, datetime

from pydantic import Field

from app.shared.kernel.entity import Entity


class StoreCapabilities(Entity[str]):
    store_id: str = Field(..., description="Store context ID")
    capabilities: dict[str, bool] = Field(
        default_factory=lambda: {"has_promo_codes": False}, description="Feature flags keyed by capability name"
    )
    auto_detected: dict[str, bool] = Field(
        default_factory=dict, description="True if the capability was auto-detected (not manually overridden)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def get(self, key: str, default: bool = False) -> bool:
        return self.capabilities.get(key, default)

    def set_capability(self, key: str, value: bool, is_auto_detected: bool = True) -> None:
        self.capabilities[key] = value
        self.auto_detected[key] = is_auto_detected
        self.updated_at = datetime.now(UTC)
