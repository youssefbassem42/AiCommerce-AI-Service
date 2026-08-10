"""Widget installation domain entity.

A widget installation binds an opaque public widget key to a tenant (store). The
browser widget identifies itself with the widget key; the backend resolves the
installation and derives `store_id` / `organization_id` server-side.
"""

from datetime import UTC, datetime

from pydantic import Field

from app.shared.kernel.aggregate_root import AggregateRoot

WIDGET_STATUS_ACTIVE = "active"
WIDGET_STATUS_DISABLED = "disabled"

WIDGET_DEFAULT_SCOPES = ["rag:chat", "recommendations:read"]


class WidgetInstallation(AggregateRoot[str]):
    widget_id: str = Field(..., min_length=1, description="Public widget identifier (wid_...)")
    store_id: str = Field(..., min_length=1, description="Canonical AI tenant boundary")
    organization_id: str = Field(..., min_length=1, description="SaaS organization owning the store")
    public_key_hash: str = Field(..., min_length=1, description="SHA-256 hash of the widget public key")
    environment: str = Field(default="live", pattern="^(live|test)$")
    status: str = Field(default=WIDGET_STATUS_ACTIVE, min_length=1)
    allowed_origins: list[str] = Field(default_factory=list, description="Merchant origins allowed to load the widget")
    scopes: list[str] = Field(default_factory=lambda: list(WIDGET_DEFAULT_SCOPES))
    last_used_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_active(self) -> bool:
        return self.status == WIDGET_STATUS_ACTIVE
