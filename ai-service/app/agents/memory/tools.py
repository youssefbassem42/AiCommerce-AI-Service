"""Tools for the Memory Agent: Redis-backed session memory and Mongo-backed user memory."""

import json
import logging
from typing import Any

from app.core.ai_settings import ai_settings
from app.domain.memory.entities.user_memory import UserMemory
from app.domain.memory.repositories.memory_repository import MemoryRepository
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.infrastructure.redis.client import RedisClient

logger = logging.getLogger(__name__)

SESSION_MEMORY_HASH = "session:{session_id}:memory"
STORE_DEFAULTS_USER_ID = "store_defaults"

_redis_client: RedisClient | None = None
_memory_repo: MemoryRepository | None = None


def _get_llm() -> BaseLLMProvider:
    return LLMProviderFactory().get_provider(ai_settings.DEFAULT_PROVIDER)


def get_redis_client() -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def get_memory_repo() -> MemoryRepository | None:
    return _memory_repo


def set_memory_repo(repo: MemoryRepository) -> None:
    global _memory_repo
    _memory_repo = repo


def _hash_key(session_id: str) -> str:
    return SESSION_MEMORY_HASH.format(session_id=session_id)


async def write_session_memory(
    session_id: str, key: str, value: dict[str, Any], ttl_seconds: int | None = None
) -> bool:
    """Persist a memory entry in the current Redis session hash with optional TTL."""
    client = get_redis_client()
    redis = client.client
    if not redis:
        logger.warning("Redis unavailable; skipping session memory write.")
        return False
    try:
        await redis.hset(_hash_key(session_id), key, json.dumps(value))
        if ttl_seconds is not None:
            await redis.expire(_hash_key(session_id), ttl_seconds)
        return True
    except Exception as e:
        logger.warning(f"Redis session memory write failed: {e}")
        return False


async def read_session_memory(session_id: str, key: str) -> dict[str, Any] | None:
    client = get_redis_client()
    redis = client.client
    if not redis:
        return None
    try:
        raw = await redis.hget(_hash_key(session_id), key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Redis session memory read failed: {e}")
        return None


async def list_session_memories(session_id: str) -> dict[str, Any]:
    client = get_redis_client()
    redis = client.client
    if not redis:
        return {}
    try:
        raw = await redis.hgetall(_hash_key(session_id))
        result = {}
        for key, value in raw.items():
            try:
                result[key] = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                result[key] = value
        return result
    except Exception as e:
        logger.warning(f"Redis session memory list failed: {e}")
        return {}


async def delete_session_memory(session_id: str, key: str) -> bool:
    client = get_redis_client()
    redis = client.client
    if not redis:
        return False
    try:
        return await redis.hdel(_hash_key(session_id), key) > 0
    except Exception as e:
        logger.warning(f"Redis session memory delete failed: {e}")
        return False


async def write_user_memory(
    user_id: str,
    store_id: str,
    key: str,
    value: dict[str, Any],
    ttl_seconds: int | None = None,
) -> UserMemory | None:
    """Persist a memory entry in Mongo (user_memories collection)."""
    repo = get_memory_repo()
    if not repo:
        logger.warning("MemoryRepository unavailable; skipping user memory write.")
        return None
    try:
        return await repo.upsert(user_id, store_id, key, value, ttl_seconds)
    except Exception as e:
        logger.error(f"Mongo user memory write failed: {e}")
        return None


async def read_user_memory(user_id: str, store_id: str, key: str) -> dict[str, Any] | None:
    repo = get_memory_repo()
    if not repo:
        return None
    try:
        entry = await repo.find_active_by_key(user_id, store_id, key)
        return entry.value if entry else None
    except Exception as e:
        logger.error(f"Mongo user memory read failed: {e}")
        return None


async def list_user_memories(user_id: str, store_id: str, limit: int = 50) -> dict[str, Any]:
    repo = get_memory_repo()
    if not repo:
        return {}
    try:
        entries = await repo.list_active(user_id, store_id, limit=limit)
        return {entry.key: entry.value for entry in entries}
    except Exception as e:
        logger.error(f"Mongo user memory list failed: {e}")
        return {}


async def read_store_defaults(store_id: str) -> dict[str, Any]:
    """Read store-level default memories (e.g. tone, policies)."""
    repo = get_memory_repo()
    if not repo:
        return {}
    try:
        entries = await repo.list_active(STORE_DEFAULTS_USER_ID, store_id, limit=50)
        return {entry.key: entry.value for entry in entries}
    except Exception as e:
        logger.error(f"Mongo store defaults read failed: {e}")
        return {}


async def recall_all(session_id: str, user_id: str, store_id: str) -> dict[str, Any]:
    """Recall memories by priority: current session -> user profile -> store defaults."""
    merged: dict[str, Any] = {}
    try:
        session_mem = await list_session_memories(session_id)
        user_mem = await list_user_memories(user_id, store_id)
        store_defaults = await read_store_defaults(store_id)
    except Exception as e:
        logger.error(f"Memory recall failed: {e}")
        return merged

    merged.update(store_defaults)
    merged.update(user_mem)
    merged.update(session_mem)

    # Session summaries are user-scoped but per-conversation: only the current
    # session's summary is recalled, so parallel conversations of the same
    # customer+store never see each other's summaries (Phase 4). The legacy
    # un-scoped "session_summary" key is kept for backward compatibility.
    own_summary_key = f"session_summary:{session_id}" if session_id else None
    for key in [k for k in merged if k.startswith("session_summary:")]:
        if key != own_summary_key:
            del merged[key]
    return merged


async def summarize_transcript(transcript: str, llm: BaseLLMProvider | None = None) -> dict[str, Any]:
    """Summarize a conversation transcript into structured memory via the LLM."""
    provider = llm or _get_llm()
    from app.application.dto.ai_dto import ChatRequest, MessageDTO
    from app.infrastructure.prompts.client import get_prompt_client

    prompt = await get_prompt_client().get("memory.summarize_session_prompt")
    request = ChatRequest(
        messages=[
            MessageDTO(
                role="system",
                content="You summarize e-commerce conversations into structured memory. Return only valid JSON.",
            ),
            MessageDTO(
                role="user",
                content=prompt.format(transcript=transcript),
            ),
        ],
        model=ai_settings.DEFAULT_MODEL,
        json_mode=True,
    )
    try:
        response = await provider.structured_output(request, dict[str, Any])
        content = response.message.content
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"raw": content}
        return content
    except Exception as e:
        logger.error(f"Session summarization failed: {e}")
        return {}


async def extract_shopping_state(
    user_input: str,
    history: str = "",
    current_state: dict[str, Any] | None = None,
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    """Extract the incremental shopping-state update from the latest message.

    Returns a plain dict with only the fields the latest message adds or
    changes; None/absent fields mean "no new information" (Fix 3.3).
    """
    provider = llm or _get_llm()
    from app.application.context.shopping_state import ShoppingState
    from app.application.dto.ai_dto import ChatRequest, MessageDTO
    from app.infrastructure.prompts.client import get_prompt_client

    current = ShoppingState.from_dict(current_state)
    prompt = await get_prompt_client().get("memory.extract_shopping_state_prompt")
    request = ChatRequest(
        messages=[
            MessageDTO(
                role="system",
                content="You track e-commerce shopping requirements across turns. Return only valid JSON.",
            ),
            MessageDTO(
                role="user",
                content=prompt.format(
                    current_state=json.dumps(current.to_dict()),
                    history=history or "(no prior conversation)",
                    user_input=user_input,
                ),
            ),
        ],
        model=ai_settings.DEFAULT_MODEL,
        json_mode=True,
    )
    try:
        response = await provider.structured_output(request, dict[str, Any])
        content = response.message.content
        data = json.loads(content) if isinstance(content, str) else content
        return ShoppingState.from_dict(data).to_dict()
    except Exception as e:
        logger.error(f"Shopping state extraction failed: {e}")
        return {}
