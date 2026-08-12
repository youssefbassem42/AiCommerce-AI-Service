from abc import ABC, abstractmethod
from typing import Any

from app.domain.analytics.entities.plan_policy import PlanPolicy
from app.shared.kernel.repository import AsyncRepository


class PlanPolicyRepository(AsyncRepository[PlanPolicy, str], ABC):
    """Repository for per-store plan policies."""

    @abstractmethod
    async def upsert(self, policy: PlanPolicy) -> PlanPolicy: ...

    @abstractmethod
    async def get_by_store(self, store_id: str) -> PlanPolicy | None: ...

    @abstractmethod
    async def update_consumer_limit(self, store_id: str, limit: int | None) -> PlanPolicy | None: ...

    @abstractmethod
    async def find_by_id(self, id: str, session: Any = None) -> PlanPolicy | None: ...
