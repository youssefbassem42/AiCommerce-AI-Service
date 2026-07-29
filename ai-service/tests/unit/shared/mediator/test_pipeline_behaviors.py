import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from app.shared.mediator.behaviors.logging import LoggingBehavior
from app.shared.mediator.behaviors.validation import ValidationBehavior
from app.shared.mediator.behaviors.authorization import AuthorizationBehavior
from app.shared.mediator.behaviors.unit_of_work import UnitOfWorkBehavior
from app.shared.mediator.behaviors.event_publisher import EventPublisherBehavior
from app.shared.cqrs.command import Command


class TestCommand(Command):
    name: str


@pytest.mark.asyncio
class TestLoggingBehavior:
    async def test_logging_delegates_to_next_handler(self, caplog):
        behavior = LoggingBehavior()
        handler = AsyncMock(return_value="result")

        result = await behavior.handle(TestCommand(name="test"), handler)

        assert result == "result"
        handler.assert_called_once()

    async def test_logging_propagates_exception(self):
        behavior = LoggingBehavior()
        handler = AsyncMock(side_effect=ValueError("fail"))

        with pytest.raises(ValueError, match="fail"):
            await behavior.handle(TestCommand(name="test"), handler)


@pytest.mark.asyncio
class TestValidationBehavior:
    async def test_no_validator_skips_validation(self):
        behavior = ValidationBehavior()
        handler = AsyncMock(return_value="ok")

        result = await behavior.handle(TestCommand(name="test"), handler)

        assert result == "ok"

    async def test_validator_passes(self):
        behavior = ValidationBehavior()
        validator = MagicMock()
        behavior.register_validator(TestCommand, validator)
        handler = AsyncMock(return_value="ok")

        result = await behavior.handle(TestCommand(name="test"), handler)

        assert result == "ok"
        validator.validate.assert_called_once()

    async def test_validator_failure_raises(self):
        behavior = ValidationBehavior()
        validator = MagicMock()
        validator.validate.side_effect = ValueError("validation failed")
        behavior.register_validator(TestCommand, validator)
        handler = AsyncMock()

        with pytest.raises(ValueError, match="validation failed"):
            await behavior.handle(TestCommand(name="test"), handler)

        handler.assert_not_called()


@pytest.mark.asyncio
class TestAuthorizationBehavior:
    async def test_no_policy_skips_authorization(self):
        behavior = AuthorizationBehavior()
        handler = AsyncMock(return_value="ok")

        result = await behavior.handle(TestCommand(name="test"), handler)

        assert result == "ok"

    async def test_policy_authorized(self):
        behavior = AuthorizationBehavior()
        policy = AsyncMock(return_value=True)
        behavior.register_policy(TestCommand, policy)
        handler = AsyncMock(return_value="ok")

        result = await behavior.handle(TestCommand(name="test"), handler)

        assert result == "ok"

    async def test_policy_denied_raises(self):
        behavior = AuthorizationBehavior()
        policy = AsyncMock(return_value=False)
        behavior.register_policy(TestCommand, policy)
        handler = AsyncMock()

        with pytest.raises(PermissionError, match="denied"):
            await behavior.handle(TestCommand(name="test"), handler)

        handler.assert_not_called()


@pytest.mark.asyncio
class TestUnitOfWorkBehavior:
    @patch("app.shared.mediator.behaviors.unit_of_work.MongoUnitOfWork")
    async def test_success_returns_handler_result(self, mock_uow):
        mock_instance = AsyncMock()
        mock_uow.return_value.__aenter__.return_value = mock_instance

        behavior = UnitOfWorkBehavior()
        handler = AsyncMock(return_value="ok")

        result = await behavior.handle(TestCommand(name="test"), handler)

        assert result == "ok"

    @patch("app.shared.mediator.behaviors.unit_of_work.MongoUnitOfWork")
    async def test_failure_propagates(self, mock_uow):
        mock_instance = AsyncMock()
        mock_uow.return_value.__aenter__.return_value = mock_instance

        behavior = UnitOfWorkBehavior()
        handler = AsyncMock(side_effect=ValueError("fail"))

        with pytest.raises(ValueError, match="fail"):
            await behavior.handle(TestCommand(name="test"), handler)


@pytest.mark.asyncio
class TestEventPublisherBehavior:
    async def test_aggregate_root_result_publishes_events(self):
        event_bus = AsyncMock()
        behavior = EventPublisherBehavior(event_bus=event_bus)
        from app.shared.kernel.aggregate_root import AggregateRoot

        class TestAgg(AggregateRoot[str]):
            name: str

        from app.shared.kernel.domain_event import DomainEvent

        class TestEvt(DomainEvent):
            data: str

        agg = TestAgg(id="agg-1", name="test")
        agg.add_domain_event(TestEvt(data="evt"))

        handler = AsyncMock(return_value=agg)

        result = await behavior.handle(TestCommand(name="test"), handler)

        event_bus.publish.assert_called_once()
        assert result.get_domain_events() == []

    async def test_non_aggregate_result_skips_publish(self):
        event_bus = AsyncMock()
        behavior = EventPublisherBehavior(event_bus=event_bus)
        handler = AsyncMock(return_value="plain_result")

        result = await behavior.handle(TestCommand(name="test"), handler)

        assert result == "plain_result"
        event_bus.publish.assert_not_called()
