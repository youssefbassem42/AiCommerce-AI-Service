"""Runtime usage persistence (spec §14, §36).

Every successful AI execution is recorded through the existing
``runtime_logs`` infrastructure (no duplicate usage records) with the fields
required for reporting: store/tenant, billing period, provider, model and
token breakdown.
"""

from __future__ import annotations

import logging

from bson import ObjectId

from app.application.dto.ai_dto import UsageDTO
from app.domain.analytics.entities.runtime_log import AIRuntimeLog
from app.domain.analytics.repositories.analytics_repository import AnalyticsRepository

logger = logging.getLogger(__name__)


class RuntimeUsageLogger:
    """Writes usage accounting records into the existing runtime log store."""

    def __init__(self, analytics_repository: AnalyticsRepository) -> None:
        self._repository = analytics_repository

    async def log(
        self,
        *,
        conversation_id: str,
        model: str,
        store_id: str,
        organization_id: str,
        billing_period: str,
        provider: str,
        usage: UsageDTO,
        latency_ms: float,
        session_id: str = "",
        level: str = "INFO",
        message: str = "AI execution completed",
        details: dict | None = None,
    ) -> None:
        entity = AIRuntimeLog(
            id=str(ObjectId()),
            conversation_id=conversation_id or "",
            model=model,
            prompt_tokens=str(max(0, int(usage.prompt_tokens or 0))),
            latency=float(latency_ms or 0.0),
            level=level,
            message=message,
            details=details or {},
            store_id=store_id,
            organization_id=organization_id,
            billing_period=billing_period,
            provider=provider,
            completion_tokens=max(0, int(usage.completion_tokens or 0)),
            total_tokens=max(0, int(usage.total_tokens or 0)),
            cost=float(usage.cost or 0.0),
            session_id=session_id,
        )
        try:
            await self._repository.create(entity)
        except Exception as exc:
            logger.error("Failed to persist runtime usage log: %s", exc)
