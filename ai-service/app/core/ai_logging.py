"""Structured AI flow-event logging.

Every hop of an AI chat turn emits one structured event (JSON, key=value
serialized) under the "ai.flow" logger so a single `message_id` can be traced
end to end: flow start -> conversation -> intent -> retrieval -> agent result
-> response. `request_id` is attached automatically from the request context.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.request_context import get_request_id

_flow_logger = logging.getLogger("ai.flow")


def log_flow_event(event: str, **fields: Any) -> None:
    """Emit one structured flow event with the current request_id attached."""
    payload: dict[str, Any] = {"event": event, "request_id": get_request_id()}
    payload.update(fields)
    _flow_logger.info(json.dumps(payload, default=str, sort_keys=True))
