from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import Field

from app.shared.kernel.aggregate_root import AggregateRoot


class UserMemory(AggregateRoot[str]):
    """Domain entity representing a persisted user memory entry (session/user-level)."""

    user_id: str = Field(..., description="ID of the user the memory belongs to")
    store_id: str = Field(..., description="Commerce store context ID")
    key: str = Field(..., description="Memory key (e.g. preferred_brand, last_product_viewed)")
    value: dict[str, Any] = Field(..., description="Structured memory value")
    ttl_seconds: int | None = Field(None, description="Optional time-to-live in seconds; None means persistent")
    expires_at: datetime | None = Field(None, description="Absolute expiry timestamp derived from ttl_seconds")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_expired(self) -> bool:
        """Whether the memory entry has passed its expiry timestamp."""
        if not self.expires_at:
            return False
        return datetime.now(UTC) > self.expires_at

    def touch(self, ttl_seconds: int | None = None) -> None:
        """Refresh updated_at and recompute expires_at (optionally with a new TTL)."""
        self.updated_at = datetime.now(UTC)
        if ttl_seconds is not None:
            self.ttl_seconds = ttl_seconds
        if self.ttl_seconds is not None:
            self.expires_at = self.updated_at + timedelta(seconds=self.ttl_seconds)
        else:
            self.expires_at = None
