from typing import Any, Dict, List, Optional, Type, TypeVar
import logging

from app.shared.cqrs.command import Command
from app.shared.cqrs.query import Query
from app.shared.cqrs.command_handler import CommandHandler
from app.shared.cqrs.query_handler import QueryHandler
from app.shared.cqrs.result import CommandResult, QueryResult
from app.shared.mediator.pipeline import PipelineBehavior, NextHandler

logger = logging.getLogger(__name__)

TCommand = TypeVar("TCommand", bound=Command)
TQuery = TypeVar("TQuery", bound=Query)
TEvent = TypeVar("TEvent")


class Mediator:
    def __init__(self):
        self._command_handlers: Dict[Type[Command], CommandHandler] = {}
        self._query_handlers: Dict[Type[Query], QueryHandler] = {}
        self._event_handlers: Dict[Type[Any], List[Any]] = {}
        self._behaviors: List[PipelineBehavior] = []

    def register_handler(self, command_type: Type[TCommand], handler: CommandHandler[TCommand, Any]) -> None:
        self._command_handlers[command_type] = handler

    def register_query_handler(self, query_type: Type[TQuery], handler: QueryHandler[TQuery, Any]) -> None:
        self._query_handlers[query_type] = handler

    def register_event_handler(self, event_type: Type[TEvent], handler: Any) -> None:
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def unregister_event_handler(self, event_type: Type[TEvent], handler: Any) -> None:
        if event_type in self._event_handlers:
            self._event_handlers[event_type] = [h for h in self._event_handlers[event_type] if h is not handler]
            if not self._event_handlers[event_type]:
                del self._event_handlers[event_type]

    def add_behavior(self, behavior: PipelineBehavior) -> None:
        self._behaviors.append(behavior)
        self._behaviors.sort(key=lambda b: b.order)

    async def send(self, command: Command) -> CommandResult:
        handler = self._command_handlers.get(type(command))
        if not handler:
            logger.error("No handler registered for command: %s", type(command).__name__)
            return CommandResult(
                success=False,
                error=f"No handler registered for command: {type(command).__name__}",
                correlation_id=command.correlation_id,
            )
        try:
            result = await self._run_through_pipeline(command, handler)
            return CommandResult(
                success=True,
                data=result,
                correlation_id=command.correlation_id,
            )
        except Exception as e:
            logger.exception("Command %s failed: %s", type(command).__name__, str(e))
            return CommandResult(
                success=False,
                error=str(e),
                correlation_id=command.correlation_id,
            )

    async def ask(self, query: Query) -> QueryResult:
        handler = self._query_handlers.get(type(query))
        if not handler:
            logger.error("No handler registered for query: %s", type(query).__name__)
            return QueryResult(
                success=False,
                error=f"No handler registered for query: {type(query).__name__}",
                correlation_id=query.correlation_id,
            )
        try:
            result = await self._run_through_pipeline(query, handler)
            return QueryResult(
                success=True,
                data=result,
                correlation_id=query.correlation_id,
            )
        except Exception as e:
            logger.exception("Query %s failed: %s", type(query).__name__, str(e))
            return QueryResult(
                success=False,
                error=str(e),
                correlation_id=query.correlation_id,
            )

    async def publish(self, event: Any) -> None:
        handlers = self._event_handlers.get(type(event), [])
        if not handlers:
            logger.debug("No handlers registered for event: %s", type(event).__name__)
            return
        for handler in handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                logger.exception(
                    "Event handler %s failed for event %s: %s",
                    handler.__class__.__name__,
                    type(event).__name__,
                    str(e),
                )

    async def _run_through_pipeline(self, request: Any, handler: Any) -> Any:
        async def invoke_handler() -> Any:
            return await handler.handle(request)

        chain: NextHandler = invoke_handler
        for behavior in reversed(self._behaviors):
            current_behavior = behavior
            next_in_chain = chain

            async def make_handler(b: PipelineBehavior, n: NextHandler) -> NextHandler:
                async def handler_wrapper() -> Any:
                    return await b.handle(request, n)
                return handler_wrapper

            chain = await make_handler(current_behavior, next_in_chain)

        return await chain()
