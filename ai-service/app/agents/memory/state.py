from typing import Any, TypedDict


class MemoryState(TypedDict, total=False):
    """State for the Memory Agent graph."""

    action: str
    session_id: str | None
    user_id: str | None
    store_id: str | None
    key: str | None
    value: dict[str, Any] | None
    ttl_seconds: int | None
    retrieved: dict[str, Any] | None
    summarized: str | None
    result: dict[str, Any] | None
    error: str | None
