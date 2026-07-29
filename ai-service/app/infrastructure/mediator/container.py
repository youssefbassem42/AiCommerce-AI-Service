from fastapi import Depends

from app.shared.mediator.mediator import Mediator
from app.shared.mediator.behaviors.logging import LoggingBehavior
from app.shared.mediator.behaviors.validation import ValidationBehavior


_mediator: Mediator | None = None


def create_mediator() -> Mediator:
    global _mediator
    if _mediator is None:
        _mediator = Mediator()
        _mediator.add_behavior(LoggingBehavior())
        _mediator.add_behavior(ValidationBehavior())
    return _mediator


def get_mediator() -> Mediator:
    mediator = create_mediator()
    return mediator


def reset_mediator() -> None:
    global _mediator
    _mediator = None
