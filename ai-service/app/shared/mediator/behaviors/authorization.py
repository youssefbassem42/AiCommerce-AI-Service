import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.shared.mediator.pipeline import NextHandler, PipelineBehavior

logger = logging.getLogger(__name__)


class AuthorizationBehavior(PipelineBehavior):
    order: int = -500

    def __init__(self, policies: dict[type, Callable[[Any], Awaitable[bool]]] | None = None):
        self._policies: dict[type, Callable[[Any], Awaitable[bool]]] = policies or {}

    def register_policy(self, request_type: type, policy: Callable[[Any], Awaitable[bool]]) -> None:
        self._policies[request_type] = policy

    async def handle(self, request: Any, next_handler: NextHandler) -> Any:
        policy = self._policies.get(type(request))
        if policy:
            authorized = await policy(request)
            if not authorized:
                raise PermissionError(f"Authorization denied for {type(request).__name__}")
        return await next_handler()
