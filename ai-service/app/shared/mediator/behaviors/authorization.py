from typing import Any, Awaitable, Callable, Dict, Optional, Type
import logging

from app.shared.mediator.pipeline import PipelineBehavior, NextHandler

logger = logging.getLogger(__name__)


class AuthorizationBehavior(PipelineBehavior):
    order: int = -500

    def __init__(self, policies: Optional[Dict[Type, Callable[[Any], Awaitable[bool]]]] = None):
        self._policies: Dict[Type, Callable[[Any], Awaitable[bool]]] = policies or {}

    def register_policy(self, request_type: Type, policy: Callable[[Any], Awaitable[bool]]) -> None:
        self._policies[request_type] = policy

    async def handle(self, request: Any, next_handler: NextHandler) -> Any:
        policy = self._policies.get(type(request))
        if policy:
            authorized = await policy(request)
            if not authorized:
                raise PermissionError(f"Authorization denied for {type(request).__name__}")
        return await next_handler()
