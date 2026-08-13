import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.analytics.dependencies import (
    get_bearer_token,
    get_net_backend_client,
    get_sentiment_analytics_service,
    require_admin_role,
)
from app.api.analytics.schemas import (
    AIUsageBillingPeriodSchema,
    AIUsageResponse,
    AIUsageTokensSchema,
    ConsumerDailyLimitResponse,
    ConsumerDailyLimitSchema,
    DailyAllowedMessageResponse,
    SentimentSummaryResponse,
    SubscriptionPlanResponse,
)
from app.api.auth.dependencies import get_current_store_id
from app.api.quota.dependencies import get_plan_policy_service, get_usage_reporting_service
from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService
from app.application.quota.plan_policy import ConsumerLimitOutOfRangeError, PlanPolicyService
from app.application.quota.usage_reporting import UsageReport, UsageReportingService
from app.core.security import ERR_NO_STORE
from app.infrastructure.net.backend_client import NetBackendClient, NetBackendError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics"],
    dependencies=[Depends(require_admin_role)],
)


@router.get(
    "/sentiment-summary",
    response_model=SentimentSummaryResponse,
    summary="Get sentiment breakdown for store tickets (admin only)",
)
async def get_sentiment_summary(
    service: SentimentAnalyticsService = Depends(get_sentiment_analytics_service),
    claimed_store_id: str = Depends(get_current_store_id),
    store_id: str | None = Query(
        default=None,
        description=("Store identifier; if provided it MUST match the authenticated user's store claim"),
    ),
) -> SentimentSummaryResponse:
    """Cross-store protection: the store is resolved from the validated JWT claim.

    A client-supplied `store_id` that does not match the claim is a tenant
    manipulation attempt and is denied — analytics data is store-scoped.
    """
    if store_id and store_id != claimed_store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERR_NO_STORE,
        )
    try:
        result = await service.get_sentiment_summary(claimed_store_id)
        return SentimentSummaryResponse(**result.model_dump())
    except Exception as exc:
        logger.error("Failed to get sentiment summary: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sentiment summary: {exc}",
        )


@router.get(
    "/ai-usage",
    response_model=AIUsageResponse,
    summary="Get store AI usage report (plan, billing period, token quota, provider/model breakdown)",
)
async def get_ai_usage(
    service: UsageReportingService = Depends(get_usage_reporting_service),
    claimed_store_id: str = Depends(get_current_store_id),
    store_id: str | None = Query(
        default=None,
        description=("Store identifier; if provided it MUST match the authenticated user's store claim"),
    ),
) -> AIUsageResponse:
    """Store-scoped AI usage report (spec §22, §46).

    Cross-store protection mirrors the sentiment endpoint: any client-supplied
    `store_id` must match the validated JWT claim.
    """
    if store_id and store_id != claimed_store_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_NO_STORE)
    report: UsageReport = await service.report(claimed_store_id)
    return _to_usage_response(claimed_store_id, report)


@router.put(
    "/ai-usage/consumer-limit",
    response_model=ConsumerDailyLimitResponse,
    summary="Set the store's consumer daily message limit (store owner, write-through to .NET)",
)
async def set_consumer_daily_limit(
    payload: ConsumerDailyLimitSchema,
    request: Request,
    claimed_store_id: str = Depends(get_current_store_id),
    plan_service: PlanPolicyService = Depends(get_plan_policy_service),
    net_client: NetBackendClient = Depends(get_net_backend_client),
) -> ConsumerDailyLimitResponse:
    """Store-owner consumer daily limit configuration (spec §52).

    The override is written through to the .NET backend (source of truth) with
    the caller's Bearer token; the local policy is updated only after .NET
    confirms. Validation: ``0 <= limit <= plan.consumer_daily_message_limit_max``.
    """
    try:
        policy = await plan_service.set_consumer_daily_limit(
            claimed_store_id,
            payload.consumer_daily_message_limit,
            net_client=net_client,
            token=get_bearer_token(request),
        )
    except ConsumerLimitOutOfRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"consumer_daily_message_limit must satisfy 0 <= {exc.requested} <= {exc.hard_max}",
        ) from exc
    except NetBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Plan backend unavailable: {exc}",
        ) from exc
    return ConsumerDailyLimitResponse(
        store_id=claimed_store_id,
        consumer_daily_message_limit=policy.effective_consumer_daily_limit,
        consumer_daily_message_limit_max=policy.consumer_daily_message_limit_max,
    )


@router.get(
    "/ai-usage/daily-message-limit",
    response_model=DailyAllowedMessageResponse,
    summary="Get the store's daily allowed message limit from .NET (refreshes local policy)",
)
async def get_daily_allowed_message(
    request: Request,
    claimed_store_id: str = Depends(get_current_store_id),
    plan_service: PlanPolicyService = Depends(get_plan_policy_service),
    net_client: NetBackendClient = Depends(get_net_backend_client),
) -> DailyAllowedMessageResponse:
    """Proxy ``GET /api/stores/{storeId}/daily-allowed-message``.

    On success the fetched entitlement also refreshes the local plan policy
    (``source=net``). If .NET is unreachable the response degrades to the
    locally persisted policy (``source=local``).
    """
    token = get_bearer_token(request)
    try:
        daily_msg = await net_client.get_daily_allowed_message(claimed_store_id, token)
        plan_data = await net_client.get_subscription_plan(token)
        await plan_service.sync_from_net(
            plan_data,
            claimed_store_id,
            daily_msg=daily_msg,
        )
        return DailyAllowedMessageResponse(
            store_id=claimed_store_id,
            daily_allowed_message=daily_msg.daily_allowed_message,
            plan_daily_allowed_message=daily_msg.plan_daily_allowed_message,
            store_override=daily_msg.store_override,
            source="net",
        )
    except NetBackendError as exc:
        logger.warning("Net backend daily-message-limit failed, using local policy: %s", exc)
        policy = await plan_service.resolve(claimed_store_id)
        return DailyAllowedMessageResponse(
            store_id=claimed_store_id,
            daily_allowed_message=policy.effective_consumer_daily_limit,
            plan_daily_allowed_message=policy.consumer_daily_message_limit_max,
            store_override=policy.consumer_daily_message_limit,
            source="local",
        )


@router.get(
    "/ai-usage/subscription-plan",
    response_model=SubscriptionPlanResponse,
    summary="Get the store's subscription plan from .NET (refreshes local policy)",
)
async def get_subscription_plan(
    request: Request,
    claimed_store_id: str = Depends(get_current_store_id),
    plan_service: PlanPolicyService = Depends(get_plan_policy_service),
    net_client: NetBackendClient = Depends(get_net_backend_client),
) -> SubscriptionPlanResponse:
    """Proxy ``GET /api/seller/subscriptions/User-Subscription-plan``.

    On success the entitlement also refreshes the local plan policy
    (``source=net``). If .NET is unreachable the response degrades to the
    locally persisted policy (``source=local``).
    """
    token = get_bearer_token(request)
    try:
        plan_data = await net_client.get_subscription_plan(token)
        await plan_service.sync_from_net(plan_data, claimed_store_id)
        return SubscriptionPlanResponse(
            store_id=claimed_store_id,
            subscription_status=plan_data.subscription_status,
            num_of_tokens=plan_data.num_of_tokens,
            renewal_date=plan_data.renewal_date,
            ai_models=plan_data.ai_models,
            allowed_providers=plan_data.allowed_providers,
            source="net",
        )
    except NetBackendError as exc:
        logger.warning("Net backend subscription-plan failed, using local policy: %s", exc)
        policy = await plan_service.resolve(claimed_store_id)
        return SubscriptionPlanResponse(
            store_id=claimed_store_id,
            subscription_status=policy.subscription_status,
            num_of_tokens=policy.token_limit,
            renewal_date=policy.renewal_date,
            ai_models=list(policy.allowed_models),
            allowed_providers=list(policy.allowed_providers),
            source="local",
        )


def _to_usage_response(store_id: str, report: UsageReport) -> AIUsageResponse:
    return AIUsageResponse(
        store_id=store_id,
        plan=report.plan,
        subscription_status=report.subscription_status,
        billing_period=AIUsageBillingPeriodSchema(
            id=report.billing_period,
            starts_at=report.period_start,
            ends_at=report.period_end,
            renewal_date=report.renewal_date,
        ),
        tokens=AIUsageTokensSchema(
            limit=report.token_limit,
            used=report.tokens_used,
            reserved=report.tokens_reserved,
            remaining=report.tokens_remaining,
            percentage=report.usage_percentage,
        ),
        requests=report.requests,
        prompt_tokens=report.prompt_tokens,
        completion_tokens=report.completion_tokens,
        cost_usd=report.cost,
        consumer_daily_limit=report.consumer_daily_message_limit,
        consumer_daily_limit_max=report.consumer_daily_message_limit_max,
        providers=report.providers,
        models=report.models,
    )
