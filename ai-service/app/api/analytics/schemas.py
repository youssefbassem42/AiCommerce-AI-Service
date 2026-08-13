from typing import Any

from pydantic import BaseModel, Field


class SentimentSummaryResponse(BaseModel):
    store_id: str = Field(..., description="Store identifier")
    total: int = Field(..., ge=0, description="Total tickets analyzed")
    positive_count: int = Field(..., ge=0, description="Tickets with positive sentiment")
    neutral_count: int = Field(..., ge=0, description="Tickets with neutral sentiment")
    negative_count: int = Field(..., ge=0, description="Tickets with negative sentiment")
    positive_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of positive tickets")
    neutral_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of neutral tickets")
    negative_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of negative tickets")


class AIUsageTokensSchema(BaseModel):
    limit: int = Field(..., ge=0)
    used: int = Field(..., ge=0)
    reserved: int = Field(..., ge=0)
    remaining: int = Field(..., ge=0)
    percentage: float = Field(..., ge=0.0)


class AIUsageBillingPeriodSchema(BaseModel):
    id: str = ""
    starts_at: str = ""
    ends_at: str = ""
    renewal_date: str = ""


class AIUsageResponse(BaseModel):
    """Merchant dashboard AI usage report (spec §22, §46)."""

    store_id: str = ""
    plan: str = ""
    subscription_status: str = ""
    billing_period: AIUsageBillingPeriodSchema = Field(default_factory=lambda: AIUsageBillingPeriodSchema())
    tokens: AIUsageTokensSchema = Field(default_factory=lambda: AIUsageTokensSchema())
    requests: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    consumer_daily_limit: int = Field(default=0, ge=0)
    consumer_daily_limit_max: int = Field(default=0, ge=0)
    providers: dict[str, Any] = Field(default_factory=dict)
    models: dict[str, Any] = Field(default_factory=dict)


class ConsumerDailyLimitSchema(BaseModel):
    consumer_daily_message_limit: int = Field(..., ge=0, description="Store owner configured daily message cap")


class ConsumerDailyLimitResponse(BaseModel):
    store_id: str = ""
    consumer_daily_message_limit: int = Field(default=0, ge=0)
    consumer_daily_message_limit_max: int = Field(default=0, ge=0)


class DailyAllowedMessageResponse(BaseModel):
    """Store daily message limit as reported by the .NET backend.

    ``source`` is ``net`` when served directly from .NET (and the local policy
    was refreshed), ``local`` when .NET was unreachable and the response was
    built from the locally persisted plan policy.
    """

    store_id: str = ""
    daily_allowed_message: int | None = Field(default=None, ge=0)
    plan_daily_allowed_message: int | None = Field(default=None, ge=0)
    store_override: int | None = Field(default=None, ge=0)
    source: str = "net"


class SubscriptionPlanResponse(BaseModel):
    """Subscription plan as reported by the .NET backend (source: ``net``/``local``)."""

    store_id: str = ""
    subscription_status: str = ""
    num_of_tokens: int = Field(default=0, ge=0)
    renewal_date: str = ""
    ai_models: list[str] = Field(default_factory=list)
    allowed_providers: list[str] = Field(default_factory=list)
    source: str = "net"
