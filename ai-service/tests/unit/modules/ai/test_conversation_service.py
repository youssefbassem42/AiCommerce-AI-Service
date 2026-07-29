import pytest
from unittest.mock import AsyncMock, MagicMock
from app.application.services.conversation_service import ConversationService
from app.application.dto.ai_dto import MessageDTO, UsageDTO


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_conversation = AsyncMock()
    repo.create_conversation = AsyncMock()
    repo.add_message = AsyncMock()
    return repo


@pytest.fixture
def conv_service(mock_repo):
    return ConversationService(repository=mock_repo)


@pytest.mark.asyncio
async def test_get_or_create_existing(conv_service, mock_repo):
    mock_repo.get_conversation.return_value = {"conversation_id": "conv-1", "messages": []}
    result = await conv_service.get_or_create_conversation("conv-1", "openai", "gpt-4o")
    assert result["conversation_id"] == "conv-1"
    mock_repo.create_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_new(conv_service, mock_repo):
    mock_repo.get_conversation.return_value = None
    mock_repo.create_conversation.return_value = {"conversation_id": "conv-new", "messages": []}
    result = await conv_service.get_or_create_conversation("conv-new", "openai", "gpt-4o", {"source": "test"})
    assert result["conversation_id"] == "conv-new"
    mock_repo.create_conversation.assert_called_once_with("conv-new", "openai", "gpt-4o", {"source": "test"})


@pytest.mark.asyncio
async def test_get_conversation_history(conv_service, mock_repo):
    mock_repo.get_conversation.return_value = {
        "conversation_id": "conv-1",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
    }
    messages = await conv_service.get_conversation_history("conv-1")
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Hello"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Hi there"


@pytest.mark.asyncio
async def test_get_conversation_history_empty(conv_service, mock_repo):
    mock_repo.get_conversation.return_value = None
    messages = await conv_service.get_conversation_history("nonexistent")
    assert messages == []


@pytest.mark.asyncio
async def test_save_interaction(conv_service, mock_repo):
    user_msg = MessageDTO(role="user", content="Hello")
    assistant_msg = MessageDTO(role="assistant", content="Hi back")
    usage = UsageDTO(prompt_tokens=5, completion_tokens=5, total_tokens=10, cost=0.001)

    await conv_service.save_interaction("conv-1", user_msg, assistant_msg, usage, latency_ms=50.0)

    assert mock_repo.add_message.call_count == 2
    # First call: user message
    user_call = mock_repo.add_message.call_args_list[0]
    assert user_call[0][0] == "conv-1"
    assert user_call[0][1]["role"] == "user"
    # Second call: assistant message with usage
    assistant_call = mock_repo.add_message.call_args_list[1]
    assert assistant_call[0][0] == "conv-1"
    assert assistant_call[0][1]["role"] == "assistant"
    assert assistant_call[1]["usage"] is not None
    assert assistant_call[1]["latency_ms"] == 50.0
