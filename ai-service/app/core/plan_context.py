"""Trusted plan context extracted from the .NET login access-token claims.

The .NET service is the subscription/plan authority. Its signed access token
carries the plan context (``subscriptionStatus``, ``numOfTokens``,
``aiModels``) which FastAPI trusts as the authoritative entitlement for the
store. No browser/widget-supplied value is ever consulted.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.ai_settings import ai_settings
from app.core.model_registry import ModelRegistry

SUBSCRIPTION_STATUS_CLAIM = "subscriptionStatus"
TOKEN_LIMIT_CLAIM = "numOfTokens"
AI_MODELS_CLAIM = "aiModels"
BILLING_PERIOD_CLAIM = "billing_period"
RENEWAL_DATE_CLAIM = "renewal_date"
CONSUMER_LIMIT_MAX_CLAIM = "consumer_daily_message_limit_max"
BILLING_PERIOD_DAYS_CLAIM = "billing_period_days"
PLAN_NAME_CLAIM = "planName"

# Provider-name aliases -> concrete default model resolved through the registry.
# .NET may send either model names or provider names in `aiModels`.
PROVIDER_DEFAULT_MODEL = {
    "openai": "gpt-4o-mini",
    "azure": "azure/gpt-4o-mini",
    "gemini": "gemini-flash-lite-latest",
    "claude": "claude-3-5-haiku-latest",
    "anthropic": "claude-3-5-haiku-latest",
    "deepseek": "deepseek-chat",
    "mistral": "mistral-large-latest",
    "ollama": "llama3",
    "openrouter": "openai/gpt-4o-mini",
}


@dataclass(frozen=True)
class PlanContext:
    """Plan entitlement resolved from trusted .NET claims."""

    store_id: str
    organization_id: str
    subscription_status: str = "Active"
    token_limit: int = 0
    allowed_models: tuple[str, ...] = ()
    allowed_providers: tuple[str, ...] = ()
    billing_period: str = ""
    renewal_date: str = ""
    consumer_daily_message_limit_max: int = 0
    billing_period_days: int = 30
    plan_name: str = ""

    @property
    def is_active(self) -> bool:
        return self.subscription_status.strip().lower() not in {"", "canceled", "cancelled", "expired", "past_due"}


def _resolve_model_alias(entry: str) -> str | None:
    """Map a raw `aiModels` entry to a concrete registry model name.

    - Exact registry model name passes through.
    - Provider/alias names resolve to that provider's default model.
    """
    if ModelRegistry.get_model_info(entry) is not None:
        return entry
    if entry in PROVIDER_DEFAULT_MODEL:
        candidate = PROVIDER_DEFAULT_MODEL[entry]
        return candidate if ModelRegistry.get_model_info(candidate) is not None else None
    return None


def parse_plan_context(claims: dict, store_id: str, organization_id: str = "") -> PlanContext:
    """Parse plan claims from a validated .NET token payload.

    Unknown/absent claims fall back to service defaults so enforcement never
    crashes on a partial token; the subscription status is never defaulted to
    active silently (see :func:`plan_is_usable`).
    """
    status = str(claims.get(SUBSCRIPTION_STATUS_CLAIM, "") or "")

    raw_limit = claims.get(TOKEN_LIMIT_CLAIM, 0)
    try:
        token_limit = int(raw_limit or 0)
    except (TypeError, ValueError):
        token_limit = 0

    raw_models = claims.get(AI_MODELS_CLAIM, [])
    if isinstance(raw_models, str):
        raw_models = [m.strip() for m in raw_models.split(",") if m.strip()]
    if not isinstance(raw_models, list):
        raw_models = []

    models: list[str] = []
    providers: list[str] = []
    for entry in raw_models:
        model = _resolve_model_alias(str(entry).strip())
        if model is None:
            continue
        if model not in models:
            models.append(model)
        info = ModelRegistry.get_model_info(model)
        if info is not None and info.provider not in providers:
            providers.append(info.provider)

    if not models:
        models = [ai_settings.DEFAULT_MODEL]
    if not providers and ModelRegistry.get_model_info(models[0]) is not None:
        providers = [ModelRegistry.get_model_info(models[0]).provider]  # type: ignore[union-attr]

    try:
        consumer_max = int(claims.get(CONSUMER_LIMIT_MAX_CLAIM, 0) or 0)
    except (TypeError, ValueError):
        consumer_max = 0

    try:
        period_days = int(claims.get(BILLING_PERIOD_DAYS_CLAIM, 0) or 0) or 30
    except (TypeError, ValueError):
        period_days = 30

    return PlanContext(
        store_id=store_id,
        organization_id=organization_id,
        subscription_status=status,
        token_limit=token_limit,
        allowed_models=tuple(models),
        allowed_providers=tuple(providers),
        billing_period=str(claims.get(BILLING_PERIOD_CLAIM, "") or ""),
        renewal_date=str(claims.get(RENEWAL_DATE_CLAIM, "") or ""),
        consumer_daily_message_limit_max=consumer_max,
        billing_period_days=max(1, period_days),
        plan_name=str(claims.get(PLAN_NAME_CLAIM, "") or ""),
    )


def plan_is_usable(plan: PlanContext) -> bool:
    """A plan with zero token limit is not a usable entitlement.

    ``numOfTokens: 0`` on a fresh account means the entitlement is not yet
    provisioned; the service must not silently grant unlimited capacity.
    """
    return plan.token_limit > 0
