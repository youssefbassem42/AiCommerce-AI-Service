from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.domain.analytics.entities.plan_policy import PlanPolicy
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class StorePlanPolicyDocument(BaseMongoDocument):
    """MongoDB document model representing the per-store plan policy."""

    store_id: str = Field(..., index=True, unique=True)
    organization_id: str = Field(default="")
    plan_name: str = Field(default="", description="Plan name supplied by .NET")
    subscription_status: str = Field(default="Active")
    token_limit: int = Field(default=0, ge=0)
    allowed_models: list[str] = Field(default_factory=list)
    allowed_providers: list[str] = Field(default_factory=list)
    billing_period: str = Field(default="")
    period_start: datetime = Field(default_factory=lambda: datetime.now(UTC))
    period_end: datetime = Field(default_factory=lambda: datetime.now(UTC))
    renewal_date: str = Field(default="")
    consumer_daily_message_limit_max: int = Field(default=0, ge=0)
    consumer_daily_message_limit: int | None = Field(default=None, ge=0)
    billing_period_days: int = Field(default=30, ge=1)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_entity(self) -> PlanPolicy:
        return PlanPolicy(
            id=str(self.id),
            store_id=self.store_id,
            organization_id=self.organization_id,
            plan_name=self.plan_name,
            subscription_status=self.subscription_status,
            token_limit=self.token_limit,
            allowed_models=tuple(self.allowed_models),
            allowed_providers=tuple(self.allowed_providers),
            billing_period=self.billing_period,
            period_start=self.period_start,
            period_end=self.period_end,
            renewal_date=self.renewal_date,
            consumer_daily_message_limit_max=self.consumer_daily_message_limit_max,
            consumer_daily_message_limit=self.consumer_daily_message_limit,
            billing_period_days=self.billing_period_days,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: PlanPolicy) -> "StorePlanPolicyDocument":
        return cls(
            store_id=entity.store_id,
            organization_id=entity.organization_id,
            plan_name=entity.plan_name,
            subscription_status=entity.subscription_status,
            token_limit=entity.token_limit,
            allowed_models=list(entity.allowed_models),
            allowed_providers=list(entity.allowed_providers),
            billing_period=entity.billing_period,
            period_start=entity.period_start,
            period_end=entity.period_end,
            renewal_date=entity.renewal_date,
            consumer_daily_message_limit_max=entity.consumer_daily_message_limit_max,
            consumer_daily_message_limit=entity.consumer_daily_message_limit,
            billing_period_days=entity.billing_period_days,
            updated_at=entity.updated_at,
        )

    @classmethod
    def from_mongo_dict(cls, data: dict[str, Any]) -> "StorePlanPolicyDocument":
        return cls.model_validate(data, from_attributes=True)
