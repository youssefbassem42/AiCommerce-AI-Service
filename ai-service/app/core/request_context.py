"""Process-wide access to the current request correlation ID.

`RequestContextMiddleware` sets the context variable for the duration of each
request; any code deeper in the stack (services, providers, logging helpers) can
read it without threading a parameter through every signature.
"""

import uuid
from contextvars import ContextVar

_current_request_id: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Correlation ID of the current request, or empty string outside a request."""
    return _current_request_id.get()


def set_request_id(request_id: str) -> None:
    _current_request_id.set(request_id)


def new_request_id() -> str:
    return str(uuid.uuid4())
