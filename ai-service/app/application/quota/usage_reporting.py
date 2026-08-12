"""Usage reporting service (spec §21-23, §37-39, §46).

Provides the merchant dashboard with plan/billing-period/token usage plus
provider and model breakdowns. Aggregations are strictly store-scoped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.application.quota.plan_policy import PlanPolicyService
from app.application.quota.store_token_quota import StoreTokenQuotaService
from app.domain.analytics.repositories.analytics_repository import AnalyticsRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsageBreakdown:
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


@dataclass(frozen=True)
class UsageReport:
    plan: str = ""
    subscription_status: str = ""
    billing_period: str = ""
    period_start: str = ""
    period_end: str = ""
    renewal_date: str = ""
    token_limit: int = 0
    tokens_used: int = 0
    tokens_reserved: int = 0
    tokens_remaining: int = 0
    usage_percentage: float = 0.0
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    consumer_daily_message_limit: int = 0
    consumer_daily_message_limit_max: int = 0
    providers: dict[str, dict] = field(default_factory=dict)
    models: dict[str, dict] = field(default_factory=dict)


class UsageReportingService:
    """Builds the tenant-scoped AI usage report for a store."""

    def __init__(
        self,
        plan_policy_service: PlanPolicyService,
        analytics_repository: AnalyticsRepository,
        store_token_quota: StoreTokenQuotaService,
    ) -> None:
        self._plan_service = plan_policy_service
        self._repository = analytics_repository
        self._quota = store_token_quota

    async def report(self, store_id: str) -> UsageReport:
        plan = await self._plan_service.resolve(store_id)
        usage = await self._repository.aggregate_usage(store_id, plan.billing_period)
        snapshot = await self._quota.snapshot(plan)

        tokens_used = int(usage["total_tokens"])
        tokens_reserved = max(0, int(snapshot.reserved))
        limit = int(plan.token_limit)

        if limit:
            used_total = tokens_used + tokens_reserved
            remaining = max(0, limit - used_total)
            percentage = round((tokens_used / limit) * 100, 2)
        else:
            remaining = 0
            percentage = 0.0

        return UsageReport(
            plan=plan.plan_name,
            subscription_status=plan.subscription_status,
            billing_period=plan.billing_period,
            period_start=plan.period_start.isoformat() if plan.period_start else "",
            period_end=plan.period_end.isoformat() if plan.period_end else "",
            renewal_date=plan.renewal_date,
            token_limit=limit,
            tokens_used=tokens_used,
            tokens_reserved=tokens_reserved,
            tokens_remaining=remaining,
            usage_percentage=percentage,
            requests=int(usage["requests"]),
            prompt_tokens=int(usage["prompt_tokens"]),
            completion_tokens=int(usage["completion_tokens"]),
            cost=float(usage["cost"]),
            consumer_daily_message_limit=plan.effective_consumer_daily_limit,
            consumer_daily_message_limit_max=plan.consumer_daily_message_limit_max,
            providers={k: dict(v) for k, v in usage["providers"].items()},
            models={k: dict(v) for k, v in usage["models"].items()},
        )
