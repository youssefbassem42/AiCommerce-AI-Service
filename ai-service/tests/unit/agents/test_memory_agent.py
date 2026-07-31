from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.memory.agent import MemoryAgent
from app.domain.memory.entities.user_memory import UserMemory
from app.infrastructure.redis.client import RedisClient


@pytest.fixture
def redis():
    client = RedisClient()
    client._redis = AsyncMock()
    yield client
    client._redis = None


@pytest.fixture
def memory_repo():
    repo = AsyncMock()
    repo.upsert.side_effect = lambda *a, **kw: _user_memory_entity(*a, **kw)
    repo.find_active_by_key.return_value = None
    repo.list_active.return_value = []
    repo.delete_by_key.return_value = True
    return repo


@pytest.fixture
def llm():
    provider = AsyncMock()
    response = MagicMock()
    response.message.content = (
        '{"key_topics": ["laptops"], "preferences": {"preferred_brand": "asus"}, '
        '"facts": {}, "intents": ["bundle"], "follow_up_items": []}'
    )
    provider.structured_output.return_value = response
    return provider


@pytest.fixture
def agent(redis, memory_repo, llm):
    return MemoryAgent(memory_repo=memory_repo, llm=llm)


class TestMemoryAgent:
    async def test_store_to_session_scope(self, agent, redis):
        result = await agent.store(
            key="last_product",
            value={"product_id": "p1"},
            session_id="session_1",
        )

        assert result["result"]["scope"] == "session"
        assert result["result"]["stored"] is True
        redis._redis.hset.assert_awaited_once()
        redis._redis.expire.assert_awaited_once()

    async def test_store_to_user_scope(self, agent, memory_repo):
        result = await agent.store(
            key="preferred_brand",
            value={"brand": "asus"},
            user_id="user_1",
            store_id="store_1",
            ttl_seconds=3600,
        )

        assert result["result"]["scope"] == "user"
        memory_repo.upsert.assert_awaited_once()

    async def test_store_requires_key_and_value(self, agent):
        result = await agent.store(key=None, value=None, session_id="session_1")

        assert result["result"] is None
        assert "error" in result

    async def test_recall_specific_key_from_session(self, agent, redis):
        redis._redis.hget.return_value = '{"product_id": "p1"}'

        result = await agent.recall(key="last_product", session_id="session_1")

        assert result["retrieved"] == {
            "key": "last_product",
            "value": {"product_id": "p1"},
            "source": "session",
        }

    async def test_recall_specific_key_from_user(self, agent, memory_repo, redis):
        redis._redis.hget.return_value = None
        memory_repo.find_active_by_key.return_value = UserMemory(
            id="507f1f77bcf86cd799439011",
            user_id="user_1",
            store_id="store_1",
            key="preferred_brand",
            value={"brand": "asus"},
        )

        result = await agent.recall(
            key="preferred_brand",
            session_id="session_1",
            user_id="user_1",
            store_id="store_1",
        )

        assert result["retrieved"]["source"] == "user"
        assert result["retrieved"]["value"] == {"brand": "asus"}

    async def test_recall_merged_without_key(self, agent, memory_repo, redis):
        redis._redis.hgetall.return_value = {"last_product": '{"product_id": "p2"}'}
        memory_repo.list_active.return_value = [
            UserMemory(
                id="507f1f77bcf86cd799439012",
                user_id="user_1",
                store_id="store_1",
                key="preferred_brand",
                value={"brand": "dell"},
            )
        ]

        result = await agent.recall(
            session_id="session_1",
            user_id="user_1",
            store_id="store_1",
        )

        assert result["retrieved"]["source"] == "merged"
        assert result["retrieved"]["all"]["last_product"] == {"product_id": "p2"}
        assert result["retrieved"]["all"]["preferred_brand"] == {"brand": "dell"}

    async def test_forget_deletes_from_both_scopes(self, agent, redis, memory_repo):
        redis._redis.hdel.return_value = 1

        result = await agent.forget(
            key="preferred_brand",
            session_id="session_1",
            user_id="user_1",
            store_id="store_1",
        )

        assert result["result"]["forgotten"] is True
        assert set(result["result"]["scopes"]) == {"session", "user"}

    async def test_summarize_persists_user_summary(self, agent, memory_repo):
        result = await agent.summarize(
            transcript="user: hi\nassistant: hello",
            user_id="user_1",
            store_id="store_1",
        )

        assert result["summarized"]["preferences"] == {"preferred_brand": "asus"}
        assert result["result"]["stored"] is True
        memory_repo.upsert.assert_awaited_once()

    async def test_summarize_without_user_context_returns_summary_only(self, agent):
        result = await agent.summarize(transcript="user: hi")

        assert result["summarized"]["key_topics"] == ["laptops"]
        assert result["result"]["stored"] is False


def _user_memory_entity(user_id, store_id, key, value, ttl_seconds=None):
    entity = UserMemory(
        id="507f1f77bcf86cd799439011",
        user_id=user_id,
        store_id=store_id,
        key=key,
        value=value,
        ttl_seconds=ttl_seconds,
    )
    entity.created_at = datetime.now(UTC)
    entity.updated_at = datetime.now(UTC)
    return entity
