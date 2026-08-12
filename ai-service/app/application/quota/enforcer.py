"""Common AI runtime enforcement entry point (spec §7, §24-29, §41-42, §53).

Every AI-consuming widget request flows through :class:`QuotaEnforcer` in a
single pre-flight → reserve → execute → commit → release → log pipeline:

    resolve plan (fail closed)
    consumer session daily limit (atomic)
    store token reservation (atomic)
    LLM execution (plan-allowed providers, failover)
    commit actual usage / release unused reservation
    runtime usage log

The enforcer is the ONLY place that orchestrates quota for widget AI
execution; chat, streaming, recommendations and agents all share it. It
never accepts authoritative tenant/plan values from the client — the plan is
resolved from the trusted store entitlement and the session comes from the
validated widget token.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.application.dto.ai_dto import MessageDTO, UsageDTO
from app.application.quota.consumer_quota import ConsumerQuotaService
from app.application.quota.counter_store import QuotaUnavailableError
from app.application.quota.plan_policy import PlanPolicyService, require_usable_plan
from app.application.quota.run_context import QuotaRunState, reset_quota_run, set_quota_run
from app.application.quota.runtime_usage_logger import RuntimeUsageLogger
from app.application.quota.store_token_quota import StoreTokenQuotaService, TokenReservation
from app.application.quota.usage_normalizer import UsageNormalizer
from app.core.ai_exceptions import (
    ConsumerDailyLimitExceededException,
    QuotaUnavailableException,
    StoreTokenQuotaExceededException,
)
from app.domain.analytics.entities.plan_policy import PlanPolicy

logger = logging.getLogger(__name__)

Execute = Callable[[], Awaitable[tuple[Any, UsageDTO | None]]]


class QuotaEnforcer:
    """Pre-flight quota enforcement around an AI execution callable."""

    def __init__(
        self,
        plan_service: PlanPolicyService,
        consumer_quota: ConsumerQuotaService,
        store_quota: StoreTokenQuotaService,
        usage_logger: RuntimeUsageLogger,
    ) -> None:
        self._plan_service = plan_service
        self._consumer_quota = consumer_quota
        self._store_quota = store_quota
        self._usage_logger = usage_logger

    async def resolve_plan(self, store_id: str) -> PlanPolicy:
        """Resolve and validate the store's plan (used for policy clamping)."""
        return require_usable_plan(await self._plan_service.resolve(store_id))

    async def run(
        self,
        *,
        store_id: str,
        organization_id: str = "",
        session_id: str = "",
        conversation_id: str = "",
        echo_text: str = "",
        model: str = "",
        max_output_tokens: int | None = None,
        request_metadata: dict | None = None,
        execute: Execute,
    ) -> tuple[Any, UsageDTO]:
        """Enforce quota around ``execute`` and return ``(result, usage)``.

        Pre-flight order (spec §7):
        1. resolve plan (fail closed if not usable),
        2. consumer session daily limit (atomic),
        3. store token reservation (atomic, sized by estimated budget),
        4. only then run the LLM execution,
        5. commit actual usage and release the unused reservation,
        6. persist the runtime usage log.

        Any failure releases the reservation; quota errors are raised with
        safe, tenant-scoped details only.
        """
        plan = await self.resolve_plan(store_id)

        try:
            if session_id:
                consumer_limit = plan.effective_consumer_daily_limit
                consumer = await self._consumer_quota.reserve_message(
                    store_id=store_id,
                    session_id=session_id,
                    limit=consumer_limit,
                )
                if not consumer.ok:
                    raise ConsumerDailyLimitExceededException(
                        limit=consumer.limit,
                        used=consumer.used,
                        reset_at=consumer.reset_at.isoformat(),
                        details={
                            "store_id": store_id,
                            "session_id": session_id,
                            "reset_at": consumer.reset_at.isoformat(),
                        },
                    )

            requested_model = model or plan.fallback_model
            budget = UsageNormalizer.estimate_budget(
                messages=[MessageDTO(role="user", content=echo_text)] if echo_text else [],
                max_output_tokens=max_output_tokens,
                model=requested_model,
            )
            reservation = await self._store_quota.reserve(plan, budget)
        except QuotaUnavailableError as exc:
            # Spec §35: commercial quota must never silently become unlimited.
            raise QuotaUnavailableException(details=f"redis unavailable: {exc}") from exc
        if not reservation.ok:
            raise self._quota_exceeded_error(plan, reservation)

        run_state = QuotaRunState(store_id=store_id, plan=plan)
        set_quota_run(run_state)
        started = time.perf_counter()
        try:
            result, usage = await execute()
        except Exception:
            await self._release_on_failure(plan, reservation)
            raise
        finally:
            reset_quota_run()

        usage = self._resolve_usage(run_state, usage, result)
        snapshot = await self._store_quota.finalize(plan, reservation, usage.total_tokens)
        remaining = max(0, plan.token_limit - usage.total_tokens - snapshot.reserved)

        await self._usage_logger.log(
            conversation_id=conversation_id,
            model=requested_model,
            store_id=store_id,
            organization_id=organization_id,
            billing_period=plan.billing_period,
            provider=",".join(sorted(run_state.totals()["providers"])) or "unknown",
            usage=usage,
            latency_ms=(time.perf_counter() - started) * 1000,
            session_id=session_id,
            details={
                "quota": {
                    "limit": plan.token_limit,
                    "used": snapshot.used,
                    "reserved": snapshot.reserved,
                    "remaining": remaining,
                    "billing_period": plan.billing_period,
                },
                **(request_metadata or {}),
            },
        )
        return result, usage

    async def _release_on_failure(self, plan: PlanPolicy, reservation: TokenReservation) -> None:
        try:
            await self._store_quota.release(plan, reservation.requested)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to release reservation for store %s: %s", plan.store_id, exc)

    @staticmethod
    def _quota_exceeded_error(plan: PlanPolicy, reservation: TokenReservation) -> StoreTokenQuotaExceededException:
        return StoreTokenQuotaExceededException(
            limit=reservation.limit,
            used=reservation.used,
            details={
                "store_id": plan.store_id,
                "billing_period": plan.billing_period,
                "billing_period_end": plan.period_end.isoformat(),
                "reserved": reservation.reserved,
                "available": reservation.available,
                "limit": reservation.limit,
                "used": reservation.used,
            },
        )

    @staticmethod
    def _resolve_usage(run_state: QuotaRunState, usage: UsageDTO | None, result: Any) -> UsageDTO:
        """Actual usage for the turn.

        Preference: recorded LLM calls of the quota run (multi-call turns),
        then the caller-reported usage, then estimation from the produced text.
        """
        totals = run_state.totals()
        if run_state.llm_calls > 0:
            return UsageDTO(
                prompt_tokens=totals["prompt_tokens"],
                completion_tokens=totals["completion_tokens"],
                total_tokens=totals["total_tokens"],
                cost=round(totals["cost"], 6),
            )
        if usage is not None and usage.total_tokens:
            return UsageNormalizer.normalize_usage(usage)
        text = ""
        if result is not None:
            text = getattr(result, "response", "") or getattr(result, "rationale", "") or ""
            if isinstance(text, list):
                text = " ".join(str(part) for part in text)
        if not text:
            text = getattr(result, "message", "") if result is not None else ""
            if isinstance(text, list):
                text = " ".join(str(part) for part in text)
        if text and run_state.plan is not None:
            estimated = UsageNormalizer.estimate_from_text(str(text), run_state.plan.fallback_model)
            return estimated
        return UsageDTO(prompt_tokens=0, completion_tokens=0, total_tokens=0, cost=0.0)
