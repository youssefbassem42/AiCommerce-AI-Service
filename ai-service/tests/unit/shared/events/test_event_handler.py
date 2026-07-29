import pytest
from unittest.mock import AsyncMock

from app.shared.events.event_handler import IEventHandler
from app.shared.kernel.domain_event import DomainEvent


class TestEvent(DomainEvent):
    value: str = "data"


@pytest.mark.asyncio
class TestIEventHandler:
    async def test_handler_interface_contract(self):
        handler = AsyncMock(spec=IEventHandler)
        event = TestEvent()

        await handler.handle(event)

        handler.handle.assert_called_once_with(event)

    async def test_handler_receives_correct_event_type(self):
        handler = AsyncMock(spec=IEventHandler)
        event = TestEvent(value="specific")

        await handler.handle(event)

        handler.handle.assert_called_once_with(event)
        assert handler.handle.call_args[0][0].value == "specific"
