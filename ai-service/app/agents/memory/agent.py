"""Memory Agent: session-scoped (Redis) and user-scoped (Mongo) memory with TTL support."""

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.memory.nodes import (
    forget_memory_node,
    recall_memory_node,
    store_memory_node,
    summarize_session_node,
)
from app.agents.memory.state import MemoryState
from app.domain.memory.repositories.memory_repository import MemoryRepository
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.infrastructure.redis.client import RedisClient

logger = logging.getLogger(__name__)

NODES_BY_ACTION = {
    "store": "store_memory",
    "recall": "recall_memory",
    "forget": "forget_memory",
    "summarize": "summarize_session",
}


class MemoryAgent:
    """Manages session and user memory: store, recall, forget, and summarize."""

    def __init__(
        self,
        memory_repo: MemoryRepository | None = None,
        llm: BaseLLMProvider | None = None,
        redis_client: RedisClient | None = None,
    ):
        self._memory_repo = memory_repo
        self._llm = llm or LLMProviderFactory().get_provider("openrouter")
        self._redis_client = redis_client
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(MemoryState)

        workflow.add_node("store_memory", self._wrap(store_memory_node))
        workflow.add_node("recall_memory", self._wrap(recall_memory_node))
        workflow.add_node("forget_memory", self._wrap(forget_memory_node))
        workflow.add_node("summarize_session", self._wrap(summarize_session_node))

        workflow.add_conditional_edges(
            "__start__",
            lambda state: NODES_BY_ACTION.get(state.get("action", "recall"), "recall_memory"),
            {
                "store_memory": "store_memory",
                "recall_memory": "recall_memory",
                "forget_memory": "forget_memory",
                "summarize_session": "summarize_session",
            },
        )
        for node in ("store_memory", "recall_memory", "forget_memory", "summarize_session"):
            workflow.add_edge(node, END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: MemoryState) -> dict[str, Any]:
            return await node_fn(state, llm=self._llm)

        return wrapped

    async def _execute(self, action: str, **fields: Any) -> MemoryState:
        state: MemoryState = {
            "action": action,
            "session_id": fields.get("session_id"),
            "user_id": fields.get("user_id"),
            "store_id": fields.get("store_id"),
            "key": fields.get("key"),
            "value": fields.get("value"),
            "ttl_seconds": fields.get("ttl_seconds"),
        }
        if self._memory_repo:
            from app.agents.memory.tools import set_memory_repo

            set_memory_repo(self._memory_repo)

        result = await self._graph.ainvoke(state)
        return result

    async def store(
        self,
        key: str,
        value: dict[str, Any],
        session_id: str | None = None,
        user_id: str | None = None,
        store_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> MemoryState:
        return await self._execute(
            "store",
            session_id=session_id,
            user_id=user_id,
            store_id=store_id,
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
        )

    async def recall(
        self,
        key: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        store_id: str | None = None,
    ) -> MemoryState:
        return await self._execute(
            "recall",
            session_id=session_id,
            user_id=user_id,
            store_id=store_id,
            key=key,
        )

    async def forget(
        self,
        key: str,
        session_id: str | None = None,
        user_id: str | None = None,
        store_id: str | None = None,
    ) -> MemoryState:
        return await self._execute(
            "forget",
            session_id=session_id,
            user_id=user_id,
            store_id=store_id,
            key=key,
        )

    async def summarize(
        self,
        transcript: str,
        session_id: str | None = None,
        user_id: str | None = None,
        store_id: str | None = None,
    ) -> MemoryState:
        return await self._execute(
            "summarize",
            session_id=session_id,
            user_id=user_id,
            store_id=store_id,
            value={"transcript": transcript},
        )

    async def run(self, state: MemoryState) -> MemoryState:
        """Graph entrypoint for direct/coordinator invocation."""
        return await self._graph.ainvoke(state)
