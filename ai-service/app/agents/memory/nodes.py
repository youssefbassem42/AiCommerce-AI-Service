"""Nodes for the Memory Agent graph."""

import logging
from typing import Any

from app.agents.memory.state import MemoryState
from app.agents.memory.tools import (
    delete_session_memory,
    list_session_memories,
    read_session_memory,
    recall_all,
    summarize_transcript,
    write_session_memory,
    write_user_memory,
)
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

SESSION_TTL_DEFAULT = 60 * 60 * 24  # 24h session retention


async def store_memory_node(state: MemoryState, **deps: Any) -> dict[str, Any]:
    """Persist a memory entry: session-scoped (Redis) or user-scoped (Mongo)."""
    key = state.get("key")
    value = state.get("value")
    if not key or value is None:
        return {"error": "store_memory requires 'key' and 'value'", "result": None}

    session_id = state.get("session_id")
    user_id = state.get("user_id")
    store_id = state.get("store_id")
    ttl = state.get("ttl_seconds")

    try:
        if session_id and not user_id:
            ok = await write_session_memory(session_id, key, value, ttl or SESSION_TTL_DEFAULT)
            if not ok:
                return {"error": "Failed to write session memory", "result": None}
            return {"result": {"stored": True, "scope": "session", "key": key}}

        if user_id and store_id:
            entry = await write_user_memory(user_id, store_id, key, value, ttl)
            if entry is None:
                return {"error": "Failed to write user memory", "result": None}
            return {"result": {"stored": True, "scope": "user", "key": key, "id": entry.id}}

        return {"error": "store_memory requires session_id or (user_id, store_id)", "result": None}
    except Exception as e:
        logger.error(f"store_memory_node failed: {e}")
        return {"error": str(e), "result": None}


async def recall_memory_node(state: MemoryState, **deps: Any) -> dict[str, Any]:
    """Recall memory with priority: current session -> user profile -> store defaults."""
    session_id = state.get("session_id")
    user_id = state.get("user_id")
    store_id = state.get("store_id")
    key = state.get("key")

    try:
        if key:
            if session_id:
                session_value = await read_session_memory(session_id, key)
                if session_value is not None:
                    return {"retrieved": {"key": key, "value": session_value, "source": "session"}}

            if user_id and store_id:
                user_value = await _read_user_memory(user_id, store_id, key)
                if user_value is not None:
                    return {"retrieved": {"key": key, "value": user_value, "source": "user"}}

            return {"retrieved": None}

        if session_id and user_id and store_id:
            memories = await recall_all(session_id, user_id, store_id)
            return {"retrieved": {"all": memories, "source": "merged"}}

        if session_id:
            memories = await list_session_memories(session_id)
            return {"retrieved": {"all": memories, "source": "session"}}

        return {"retrieved": None}
    except Exception as e:
        logger.error(f"recall_memory_node failed: {e}")
        return {"error": str(e), "retrieved": None}


async def _read_user_memory(user_id: str | None, store_id: str | None, key: str) -> dict[str, Any] | None:
    if not user_id or not store_id:
        return None
    from app.agents.memory.tools import read_user_memory

    return await read_user_memory(user_id, store_id, key)


async def forget_memory_node(state: MemoryState, **deps: Any) -> dict[str, Any]:
    """Delete a memory entry from session (Redis) and/or user (Mongo) scope."""
    key = state.get("key")
    if not key:
        return {"error": "forget_memory requires 'key'", "result": None}

    session_id = state.get("session_id")
    user_id = state.get("user_id")
    store_id = state.get("store_id")

    deleted = []
    try:
        if session_id and await delete_session_memory(session_id, key):
            deleted.append("session")
        if user_id and store_id:
            from app.agents.memory.tools import get_memory_repo

            repo = get_memory_repo()
            if repo and await repo.delete_by_key(user_id, store_id, key):
                deleted.append("user")
        return {"result": {"forgotten": bool(deleted), "scopes": deleted}}
    except Exception as e:
        logger.error(f"forget_memory_node failed: {e}")
        return {"error": str(e), "result": None}


async def summarize_session_node(state: MemoryState, **deps: Any) -> dict[str, Any]:
    """Summarize the current session transcript and persist it as a user-level memory."""
    session_id = state.get("session_id")
    user_id = state.get("user_id")
    store_id = state.get("store_id")
    transcript = state.get("value", {}).get("transcript") if state.get("value") else None

    if not transcript:
        if session_id:
            memories = await list_session_memories(session_id)
            transcript = "\n".join(f"{k}: {v}" for k, v in memories.items())
        if not transcript:
            return {"error": "summarize_session requires a transcript or session memories", "summarized": None}

    llm: BaseLLMProvider | None = deps.get("llm")
    summary = await summarize_transcript(transcript, llm)

    if user_id and store_id:
        # Key the summary per conversation: parallel conversations of the
        # same customer+store must not overwrite each other's summaries
        # (Phase 4). `recall_all` filters out other sessions' summaries.
        summary_key = f"session_summary:{session_id}" if session_id else "session_summary"
        entry = await write_user_memory(user_id, store_id, summary_key, summary)
        if entry:
            return {"summarized": summary, "result": {"stored": True, "key": summary_key}}

    return {"summarized": summary, "result": {"stored": False}}
