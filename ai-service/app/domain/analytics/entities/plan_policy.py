from datetime import UTC, datetime

from pydantic import Field, computed_field, field_validator

from app.shared.kernel.aggregate_root import AggregateRoot


def ensure_aware_utc(value: datetime) -> datetime:
    """Treat legacy offset-naive UTC datetimes as aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class PlanPolicy(AggregateRoot[str]):
    """Per-store plan policy — the runtime enforcement entitlement.

    The plan itself is centrally configured by .NET/Super Admin; FastAPI
    receives it through the trusted login token claims (see
    ``app.core.plan_context``) and persists it here as the runtime policy.

    ``billing_period`` is the subscription billing period identity supplied by
    .NET. When .NET does not supply one (yet), the AI service derives a period
    anchored at first provision and rolls it on ``period_end``.
    """

    store_id: str = Field(..., description="Store this policy belongs to")
    organization_id: str = Field(default="")
    plan_name: str = Field(default="", description="Plan name supplied by .NET")
    subscription_status: str = Field(default="Active")
    token_limit: int = Field(default=0, ge=0, description="Tokens per billing period")
    allowed_models: tuple[str, ...] = Field(default=(), description="Plan allowed models")
    allowed_providers: tuple[str, ...] = Field(default=(), description="Plan allowed providers")
    billing_period: str = Field(default="", description="Subscription billing period identity")
    period_start: datetime = Field(default_factory=lambda: datetime.now(UTC))
    period_end: datetime = Field(default_factory=lambda: datetime.now(UTC))
    renewal_date: str = Field(default="", description="Renewal date supplied by .NET")
    consumer_daily_message_limit_max: int = Field(default=0, ge=0)
    consumer_daily_message_limit: int | None = Field(default=None, ge=0)
    billing_period_days: int = Field(default=30, ge=1)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("period_start", "period_end", "updated_at", mode="before")
    @classmethod
    def _coerce_naive_utc(cls, value):
        """Legacy persisted policies store offset-naive UTC datetimes.

        Comparisons against aware ``now`` raised ``TypeError``; naive values
        are treated as UTC on load so every downstream use is consistent.
        """
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def subscription_active(self) -> bool:
        return self.subscription_status.strip().lower() not in {"", "canceled", "cancelled", "expired", "past_due"}

    @property
    def effective_consumer_daily_limit(self) -> int:
        """Store-owner override, capped by the plan hard maximum."""
        if self.consumer_daily_message_limit is None:
            return max(0, self.consumer_daily_message_limit_max)
        return max(0, min(self.consumer_daily_message_limit, self.consumer_daily_message_limit_max))

    @property
    def fallback_model(self) -> str:
        if self.allowed_models:
            return self.allowed_models[0]
        return ""

    @property
    def has_plan_claims(self) -> bool:
        """True when the policy carries real entitlement data.

        Policies synced from tokens without plan claims are empty shells
        (``subscription_status``/``plan_name`` empty, zero token limit, no
        models); they are not entitlements and must not be enforced.
        """
        return bool(
            self.subscription_status
            or self.plan_name
            or self.renewal_date
            or self.token_limit > 0
            or self.allowed_models
            or self.allowed_providers
            or self.consumer_daily_message_limit_max > 0
        )

    def period_expired(self, now: datetime | None = None) -> bool:
        now = ensure_aware_utc(now or datetime.now(UTC))
        return now >= ensure_aware_utc(self.period_end)
