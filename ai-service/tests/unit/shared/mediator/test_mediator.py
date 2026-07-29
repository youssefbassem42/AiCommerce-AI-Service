import pytest
from unittest.mock import AsyncMock, MagicMock

from app.shared.cqrs.command import Command
from app.shared.cqrs.query import Query
from app.shared.cqrs.command_handler import CommandHandler
from app.shared.cqrs.query_handler import QueryHandler
from app.shared.cqrs.result import CommandResult, QueryResult
from app.shared.mediator.mediator import Mediator
from app.shared.mediator.pipeline import PipelineBehavior


class TestCommand(Command):
    value: str


class TestQuery(Query):
    value: str


class TestCommandHandler(CommandHandler[TestCommand, str]):
    async def handle(self, command: TestCommand) -> str:
        return f"handled:{command.value}"


class TestQueryHandler(QueryHandler[TestQuery, str]):
    async def handle(self, query: TestQuery) -> str:
        return f"queried:{query.value}"


class TestBehavior(PipelineBehavior):
    order: int = 0

    async def handle(self, request, next_handler):
        result = await next_handler()
        return f"behavior({result})"


@pytest.mark.asyncio
class TestMediator:
    async def test_send_command_success(self):
        mediator = Mediator()
        mediator.register_handler(TestCommand, TestCommandHandler())

        result = await mediator.send(TestCommand(value="test"))

        assert result.success is True
        assert result.data == "handled:test"
        assert result.error is None

    async def test_send_command_no_handler(self):
        mediator = Mediator()

        result = await mediator.send(TestCommand(value="test"))

        assert result.success is False
        assert result.error is not None
        assert "No handler" in result.error

    async def test_ask_query_success(self):
        mediator = Mediator()
        mediator.register_query_handler(TestQuery, TestQueryHandler())

        result = await mediator.ask(TestQuery(value="test"))

        assert result.success is True
        assert result.data == "queried:test"

    async def test_ask_query_no_handler(self):
        mediator = Mediator()

        result = await mediator.ask(TestQuery(value="test"))

        assert result.success is False
        assert "No handler" in result.error

    async def test_publish_event_with_handlers(self):
        mediator = Mediator()
        handler = AsyncMock()
        mediator.register_event_handler(TestCommand, handler)

        event = TestCommand(value="event-data")
        await mediator.publish(event)

        handler.handle.assert_called_once_with(event)

    async def test_publish_event_no_handlers(self):
        mediator = Mediator()

        await mediator.publish(TestCommand(value="event-data"))

    async def test_send_with_pipeline_behavior(self):
        mediator = Mediator()
        mediator.register_handler(TestCommand, TestCommandHandler())
        mediator.add_behavior(TestBehavior())

        result = await mediator.send(TestCommand(value="test"))

        assert result.success is True
        assert result.data == "behavior(handled:test)"

    async def test_ask_with_pipeline_behavior(self):
        mediator = Mediator()
        mediator.register_query_handler(TestQuery, TestQueryHandler())
        mediator.add_behavior(TestBehavior())

        result = await mediator.ask(TestQuery(value="test"))

        assert result.success is True
        assert result.data == "behavior(queried:test)"

    async def test_multiple_behaviors_execute_in_order(self):
        class FirstBehavior(PipelineBehavior):
            order: int = 0
            async def handle(self, request, next_handler):
                result = await next_handler()
                return f"first({result})"

        class SecondBehavior(PipelineBehavior):
            order: int = 1
            async def handle(self, request, next_handler):
                result = await next_handler()
                return f"second({result})"

        mediator = Mediator()
        mediator.register_handler(TestCommand, TestCommandHandler())
        mediator.add_behavior(FirstBehavior())
        mediator.add_behavior(SecondBehavior())

        result = await mediator.send(TestCommand(value="test"))

        assert result.data == "first(second(handled:test))"

    async def test_handler_exception_returns_failure_result(self):
        class FailingHandler(CommandHandler[TestCommand, str]):
            async def handle(self, command: TestCommand) -> str:
                raise ValueError("handler error")

        mediator = Mediator()
        mediator.register_handler(TestCommand, FailingHandler())

        result = await mediator.send(TestCommand(value="test"))

        assert result.success is False
        assert "handler error" in result.error

    async def test_behavior_exception_propagates(self):
        class FailingBehavior(PipelineBehavior):
            order: int = 0
            async def handle(self, request, next_handler):
                raise RuntimeError("behavior error")

        mediator = Mediator()
        mediator.register_handler(TestCommand, TestCommandHandler())
        mediator.add_behavior(FailingBehavior())

        result = await mediator.send(TestCommand(value="test"))

        assert result.success is False
        assert "behavior error" in result.error

    async def test_correlation_id_preserved(self):
        mediator = Mediator()
        mediator.register_handler(TestCommand, TestCommandHandler())

        result = await mediator.send(TestCommand(value="test", correlation_id="corr-123"))

        assert result.correlation_id == "corr-123"

    async def test_unregister_event_handler(self):
        mediator = Mediator()
        handler = AsyncMock()
        mediator.register_event_handler(TestCommand, handler)
        mediator.unregister_event_handler(TestCommand, handler)

        await mediator.publish(TestCommand(value="test"))

        handler.handle.assert_not_called()
