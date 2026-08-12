"""Server-side policy for widget AI execution controls (Phase E, R-03).

The widget chat request schema exposes AI execution controls (model,
temperature, max_tokens, top_k, score_threshold, use_hybrid, use_mmr, rerank,
knowledge_scope) to an untrusted browser client. These legacy fields remain in
the contract for compatibility, but every value is run through this policy
before it can influence cost or behavior:

- model           : only server-allowlisted models pass; anything else is
                    replaced by the server default.
- temperature     : clamped into [temperature_min, temperature_max].
- max_tokens      : capped at max_tokens_max.
- top_k           : capped at top_k_max.
- use_hybrid/m    : forced off unless explicitly allowlisted.
- knowledge_scope : only allowed values pass; unknown scopes are dropped.

Every deviation is recorded and logged — never silently applied.
"""

from dataclasses import dataclass, field

from app.api.widget.schemas import WidgetChatRequestSchema
from app.core.ai_settings import ai_settings
from app.domain.analytics.entities.plan_policy import PlanPolicy


@dataclass(frozen=True)
class WidgetServerPolicy:
    """Bounds applied to widget chat AI-execution controls.

    All fields are server-side defaults; per-store policy overrides come from
    the plan policy (``widget_policy_from_plan``) — nothing here reads client
    input.
    """

    allowed_models: tuple[str, ...] = ()
    fallback_model: str = ai_settings.DEFAULT_MODEL
    temperature_min: float = 0.0
    temperature_max: float = 1.0
    max_tokens_max: int = 1024
    top_k_max: int = 10
    score_threshold_min: float = 0.0
    hybrid_allowed: bool = False
    mmr_allowed: bool = False
    rerank_allowed: bool = False
    allowed_knowledge_scopes: tuple[str, ...] = field(default_factory=tuple)


def widget_policy_from_plan(plan: PlanPolicy) -> WidgetServerPolicy:
    """Build the server-side widget AI policy from the trusted plan policy.

    Only plan-allowed models can pass; the plan fallback model replaces any
    client-supplied model (spec §19-20, §44).
    """
    return WidgetServerPolicy(
        allowed_models=tuple(plan.allowed_models) or (),
        fallback_model=plan.fallback_model or ai_settings.DEFAULT_MODEL,
    )


@dataclass(frozen=True)
class WidgetPolicyResult:
    """Policy-sanitized controls plus the list of deviations applied."""

    model: str
    temperature: float
    max_tokens: int | None
    top_k: int
    score_threshold: float
    use_hybrid: bool
    use_mmr: bool
    rerank: bool
    knowledge_scope: str | None
    clamped: tuple[str, ...] = ()


DEFAULT_WIDGET_POLICY = WidgetServerPolicy()


def apply_widget_policy(
    request: WidgetChatRequestSchema,
    policy: WidgetServerPolicy = DEFAULT_WIDGET_POLICY,
) -> WidgetPolicyResult:
    """Sanitize a widget chat request against the server policy."""
    clamped: list[str] = []
    model = request.model or policy.fallback_model
    if policy.allowed_models and model not in policy.allowed_models or not policy.allowed_models and request.model:
        clamped.append(f"model:{model}->{policy.fallback_model}")
        model = policy.fallback_model

    temperature = request.temperature if request.temperature is not None else 0.7
    if temperature < policy.temperature_min or temperature > policy.temperature_max:
        clamped_temperature = min(max(temperature, policy.temperature_min), policy.temperature_max)
        clamped.append(f"temperature:{temperature}->{clamped_temperature}")
        temperature = clamped_temperature

    max_tokens = request.max_tokens
    if max_tokens is not None and max_tokens > policy.max_tokens_max:
        clamped.append(f"max_tokens:{max_tokens}->{policy.max_tokens_max}")
        max_tokens = policy.max_tokens_max

    top_k = request.top_k
    if top_k > policy.top_k_max:
        clamped.append(f"top_k:{top_k}->{policy.top_k_max}")
        top_k = policy.top_k_max

    score_threshold = request.score_threshold
    if score_threshold < policy.score_threshold_min:
        clamped.append(f"score_threshold:{score_threshold}->{policy.score_threshold_min}")
        score_threshold = policy.score_threshold_min

    use_hybrid = request.use_hybrid and policy.hybrid_allowed
    use_mmr = request.use_mmr and policy.mmr_allowed
    rerank = request.rerank and policy.rerank_allowed
    if request.use_hybrid and not policy.hybrid_allowed:
        clamped.append("use_hybrid:True->False")
    if request.use_mmr and not policy.mmr_allowed:
        clamped.append("use_mmr:True->False")
    if request.rerank and not policy.rerank_allowed:
        clamped.append("rerank:True->False")

    knowledge_scope = request.knowledge_scope
    if knowledge_scope is not None and (
        not policy.allowed_knowledge_scopes or knowledge_scope not in policy.allowed_knowledge_scopes
    ):
        clamped.append(f"knowledge_scope:{knowledge_scope}->null")
        knowledge_scope = None

    return WidgetPolicyResult(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_k=top_k,
        score_threshold=score_threshold,
        use_hybrid=use_hybrid,
        use_mmr=use_mmr,
        rerank=rerank,
        knowledge_scope=knowledge_scope,
        clamped=tuple(clamped),
    )
