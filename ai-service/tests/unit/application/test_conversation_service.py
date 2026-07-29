from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

import pytest

from app.application.dto.ai_dto import MessageDTO, UsageDTO, ChatResponse
from app.application.services.conversation_service import ConversationService


@pytest.fixture
def conversation_repo():
    repo = AsyncMock()
    repo.get_conversation = AsyncMock()
    repo.create_conversation = AsyncMock()
    repo.add_message = AsyncMock()
    return repo


@pytest.fixture
def conversation_service(conversation_repo):
    return ConversationService(repository=conversation_repo)


class TestConversationService:

    async def test_get_conversation_history_returns_messages(self, conversation_service, conversation_repo):
        conversation_repo.get_conversation.return_value = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        }
        messages = await conversation_service.get_conversation_history("conv-1")
        assert len(messages) == 2
        assert all(isinstance(m, MessageDTO) for m in messages)
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there"

    async def test_get_conversation_history_empty_when_not_found(self, conversation_service, conversation_repo):
        conversation_repo.get_conversation.return_value = None
        messages = await conversation_service.get_conversation_history("nonexistent")
        assert messages == []

    async def test_get_conversation_history_empty_messages_list(self, conversation_service, conversation_repo):
        conversation_repo.get_conversation.return_value = {"messages": []}
        messages = await conversation_service.get_conversation_history("conv-empty")
        assert messages == []

    async def test_create_conversation_if_not_exists(self, conversation_service, conversation_repo):
        conversation_repo.get_conversation.return_value = None
        conversation_repo.create_conversation = AsyncMock()

        result = await conversation_service.get_or_create_conversation("conv-new", "s1", "c1")
        assert result is not None
        conversation_repo.create_conversation.assert_called_once()

    async def test_save_interaction_stores_user_then_assistant(self, conversation_service, conversation_repo):
        user_msg = MessageDTO(role="user", content="Hello")
        assistant_msg = MessageDTO(role="assistant", content="World")
        usage = UsageDTO(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        await conversation_service.save_interaction(
            conversation_id="conv-1",
            user_message=user_msg,
            assistant_message=assistant_msg,
            usage=usage,
            latency_ms=150,
        )

        assert conversation_repo.add_message.call_count == 2

    async def test_save_interaction_handles_tool_calls(self, conversation_service, conversation_repo):
        from app.application.dto.ai_dto import ToolCallDTO

        user_msg = MessageDTO(role="user", content="Call a tool")
        assistant_msg = MessageDTO(
            role="assistant",
            content="",
            tool_calls=[ToolCallDTO(id="call-1", type="function", function_name="get_weather", arguments='{"city":"NYC"}')],
        )
        usage = UsageDTO(prompt_tokens=5, completion_tokens=30, total_tokens=35)

        await conversation_service.save_interaction(
            conversation_id="conv-1",
            user_message=user_msg,
            assistant_message=assistant_msg,
            usage=usage,
            latency_ms=200,
        )

        assert conversation_repo.add_message.call_count == 2

    async def test_malformed_message_missing_content(self, conversation_service, conversation_repo):
        conversation_repo.get_conversation.return_value = {
            "messages": [
                {"role": "user"},
            ]
        }
        messages = await conversation_service.get_conversation_history("conv-bad")
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == ""
