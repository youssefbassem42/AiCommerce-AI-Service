"""Per-store plan policy service.

The plan is centrally configured by .NET/Super Admin; FastAPI is the runtime
enforcement authority. ``PlanPolicyService``:

1. ingests the trusted .NET login-token plan claims (``sync_from_claims``),
2. resolves the active policy for a store (Redis-cached, Mongo-backed),
3. rolls the billing period when the subscription period ends,
4. applies the store owner's consumer daily limit override.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from app.core.ai_settings import ai_settings
from app.core.config import settings
from app.core.model_registry import ModelRegistry
from app.core.plan_context import (
    AI_MODELS_CLAIM,
    BILLING_PERIOD_CLAIM,
    CONSUMER_LIMIT_MAX_CLAIM,
    PLAN_NAME_CLAIM,
    RENEWAL_DATE_CLAIM,
    SUBSCRIPTION_STATUS_CLAIM,
    TOKEN_LIMIT_CLAIM,
    PlanContext,
    parse_plan_context,
    plan_is_usable,
)
from app.domain.analytics.entities.plan_policy import PlanPolicy
from app.domain.analytics.repositories.plan_policy_repository import PlanPolicyRepository
from app.infrastructure.redis.client import RedisClient

logger = logging.getLogger(__name__)

PLAN_CACHE_PREFIX = "plan:policy:"
PLAN_CACHE_TTL_SECONDS = 300


class PlanPolicyService:
    """Resolution, ingestion and rotation of per-store plan policies."""

    def __init__(
        self,
        repository: PlanPolicyRepository,
        redis_client: RedisClient | None = None,
    ) -> None:
        self._repository = repository
        self._redis = redis_client

    async def sync_from_claims(
        self,
        claims: dict,
        store_id: str,
        organization_id: str = "",
    ) -> PlanPolicy:
        """Persist the plan entitlement carried by a validated .NET token."""
        context = parse_plan_context(claims, store_id, organization_id)

        existing = await self._repository.get_by_store(store_id)

        if not _claims_carry_plan(claims):
            # The token carries no plan data (the .NET service does not emit
            # the claims yet). Keep the existing entitlement — or fall back to
            # the usable default — instead of overwriting it with an empty,
            # unusable policy. Explicit cancel/expired statuses are never
            # produced here (they require claims to be present).
            logger.warning(
                "Login token for store %s carries no plan claims; keeping %s policy",
                store_id,
                "existing" if existing is not None else "default",
            )
            return existing if existing is not None else self._default_policy(store_id)

        now = datetime.now(UTC)

        period_id = context.billing_period
        period_start = now
        period_days = context.billing_period_days or settings.QUOTA_PERIOD_DAYS
        if existing is not None and not existing.period_expired(now):
            # Keep the active billing period; only the entitlement changes.
            period_id = period_id or existing.billing_period
            period_start = existing.period_start
            period_days = existing.billing_period_days or period_days
            if existing.renewal_date:
                period_days = existing.billing_period_days

        if not period_id:
            period_id = derived_period_id(store_id, period_start)

        policy = PlanPolicy(
            id=f"{store_id}:{period_id}",
            store_id=store_id,
            organization_id=organization_id or (existing.organization_id if existing else ""),
            plan_name=context.plan_name,
            subscription_status=context.subscription_status,
            token_limit=context.token_limit,
            allowed_models=context.allowed_models,
            allowed_providers=context.allowed_providers,
            billing_period=period_id,
            period_start=period_start,
            period_end=period_start + timedelta(days=period_days),
            renewal_date=context.renewal_date,
            consumer_daily_message_limit_max=context.consumer_daily_message_limit_max,
            consumer_daily_message_limit=existing.consumer_daily_message_limit if existing else None,
            billing_period_days=period_days,
            updated_at=now,
        )

        await self._repository.upsert(policy)
        await self._invalidate_cache(store_id)
        return policy

    async def resolve(self, store_id: str) -> PlanPolicy:
        """Resolve the active policy for a store (cache → DB → defaults)."""
        cached = await self._read_cache(store_id)
        if cached is not None and cached.has_plan_claims:
            return cached

        stored = await self._repository.get_by_store(store_id)
        if stored is not None and not stored.has_plan_claims:
            # Legacy policy persisted from a claim-less token (or from a
            # pre-claim deployment): not a real entitlement. Fall back to
            # the usable default instead of enforcing an empty shell.
            logger.warning(
                "Stored policy for store %s has no plan claims; using default entitlement",
                store_id,
            )
            stored = None
        if stored is not None:
            if stored.period_expired():
                stored = await self._roll_period(stored)
            await self._write_cache(store_id, stored)
            return stored

        policy = self._default_policy(store_id)
        await self._write_cache(store_id, policy)
        return policy

    async def set_consumer_daily_limit(self, store_id: str, limit: int) -> PlanPolicy:
        """Apply the store owner's consumer daily message limit.

        Validation: ``0 <= limit <= plan.consumer_daily_message_limit_max``.
        """
        policy = await self.resolve(store_id)
        hard_max = policy.consumer_daily_message_limit_max or settings.CONSUMER_DAILY_LIMIT_DEFAULT_MAX
        if not 0 <= limit <= hard_max:
            raise ConsumerLimitOutOfRangeError(limit, hard_max)

        updated = await self._repository.update_consumer_limit(store_id, limit)
        if updated is None:
            policy.consumer_daily_message_limit = limit
            updated = await self._repository.upsert(policy)
        await self._invalidate_cache(store_id)
        return updated

    def _default_policy(self, store_id: str) -> PlanPolicy:
        """Fail-safe entitlement before .NET provisions the store.

        Not unlimited: bounded by ``QUOTA_DEFAULT_TOKEN_LIMIT`` and the single
        default provider/model so quota enforcement is never silently disabled.
        """
        now = datetime.now(UTC)
        default_model = ai_settings.DEFAULT_MODEL
        default_provider = ai_settings.DEFAULT_PROVIDER
        info = ModelRegistry.get_model_info(default_model)
        if info is not None:
            default_provider = info.provider
        period_days = settings.QUOTA_PERIOD_DAYS
        period_start = now
        return PlanPolicy(
            id=f"{store_id}:{derived_period_id(store_id, period_start)}",
            store_id=store_id,
            organization_id="",
            plan_name="default",
            subscription_status="Active",
            token_limit=settings.QUOTA_DEFAULT_TOKEN_LIMIT,
            allowed_models=(default_model,),
            allowed_providers=(default_provider,),
            billing_period=derived_period_id(store_id, period_start),
            period_start=period_start,
            period_end=period_start + timedelta(days=period_days),
            consumer_daily_message_limit_max=settings.CONSUMER_DAILY_LIMIT_DEFAULT_MAX,
            consumer_daily_message_limit=None,
            billing_period_days=period_days,
            updated_at=now,
        )

    async def _roll_period(self, policy: PlanPolicy) -> PlanPolicy:
        """Close the active billing period and open a new quota period."""
        now = datetime.now(UTC)
        period_days = policy.billing_period_days or settings.QUOTA_PERIOD_DAYS
        policy.period_start = now
        policy.period_end = now + timedelta(days=period_days)
        policy.billing_period = derived_period_id(policy.store_id, now)
        policy.id = f"{policy.store_id}:{policy.billing_period}"
        policy.renewal_date = ""
        policy.updated_at = now
        await self._repository.upsert(policy)
        return policy

    async def _read_cache(self, store_id: str) -> PlanPolicy | None:
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(f"{PLAN_CACHE_PREFIX}{store_id}")
            if not raw:
                return None
            data = json.loads(raw)
            return PlanPolicy.model_validate(data)
        except Exception as exc:
            logger.warning("Plan policy cache read failed for store %s: %s", store_id, exc)
            return None

    async def _write_cache(self, store_id: str, policy: PlanPolicy) -> None:
        if not self._redis:
            return
        try:
            await self._redis.set(
                f"{PLAN_CACHE_PREFIX}{store_id}",
                policy.model_dump_json(),
                expire=PLAN_CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("Plan policy cache write failed for store %s: %s", store_id, exc)

    async def _invalidate_cache(self, store_id: str) -> None:
        if not self._redis:
            return
        try:
            await self._redis.delete(f"{PLAN_CACHE_PREFIX}{store_id}")
        except Exception as exc:
            logger.warning("Plan policy cache invalidation failed for store %s: %s", store_id, exc)


class ConsumerLimitOutOfRangeError(ValueError):
    """Consumer daily limit is outside the plan hard maximum."""

    def __init__(self, requested: int, hard_max: int):
        super().__init__(f"consumer_daily_message_limit must satisfy 0 <= {requested} <= {hard_max}")
        self.requested = requested
        self.hard_max = hard_max


def _claims_carry_plan(claims: dict) -> bool:
    """True when the token payload actually includes plan entitlement data."""
    keys = (
        SUBSCRIPTION_STATUS_CLAIM,
        TOKEN_LIMIT_CLAIM,
        AI_MODELS_CLAIM,
        PLAN_NAME_CLAIM,
        BILLING_PERIOD_CLAIM,
        RENEWAL_DATE_CLAIM,
        CONSUMER_LIMIT_MAX_CLAIM,
    )
    return any(bool(str(claims.get(key, "") or "")) for key in keys)


def derived_period_id(store_id: str, start: datetime) -> str:
    """AI-service derived billing period identity (used until .NET supplies one)."""
    return f"{store_id}:{start.astimezone(UTC).isoformat(timespec='seconds')}"


def require_usable_plan(policy: PlanPolicy) -> PlanPolicy:
    """Raise when the plan cannot support AI execution (fail closed)."""
    context = PlanContext(
        store_id=policy.store_id,
        organization_id=policy.organization_id,
        subscription_status=policy.subscription_status,
        token_limit=policy.token_limit,
        allowed_models=policy.allowed_models,
        allowed_providers=policy.allowed_providers,
        billing_period=policy.billing_period,
        consumer_daily_message_limit_max=policy.consumer_daily_message_limit_max,
    )
    if not context.is_active:
        raise PlanNotAvailableError("subscription")
    if not plan_is_usable(context):
        raise PlanNotAvailableError("token_limit")
    if not policy.allowed_models or not policy.allowed_providers:
        raise PlanNotAvailableError("provider_policy")
    return policy


class PlanNotAvailableError(Exception):
    """The store has no usable plan entitlement (fail closed)."""

    def __init__(self, reason: str):
        super().__init__(f"Plan not available for AI execution: {reason}")
        self.reason = reason
