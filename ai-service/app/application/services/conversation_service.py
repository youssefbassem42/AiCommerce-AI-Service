from typing import Any

from app.application.dto.ai_dto import MessageDTO, UsageDTO
from app.infrastructure.repositories.conversation_repository import ConversationRepository


class ConversationService:
    """
    Service to manage conversations, including history tracking, message appending,
    and retrieving structured messages for LLM context.
    """

    def __init__(self, repository: ConversationRepository):
        self.repository = repository

    async def get_or_create_conversation(
        self,
        conversation_id: str,
        provider: str,
        model: str,
        metadata: dict[str, Any] | None = None,
        store_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieves or creates a conversation.
        """
        conv = await self.repository.get_conversation(conversation_id)
        if not conv:
            conv = await self.repository.create_conversation(
                conversation_id, provider, model, metadata, store_id=store_id
            )
        return conv

    async def get_conversation_history(
        self,
        conversation_id: str,
        store_id: str | None = None,
    ) -> list[MessageDTO]:
        """
        Fetch conversation history as list of MessageDTOs.

        When `store_id` is provided, only conversations owned by that store are
        returned (tenant-scoped access).
        """
        conv = await self.repository.get_conversation(conversation_id, store_id=store_id)
        if not conv:
            return []

        messages = []
        for msg in conv.get("messages", []):
            messages.append(
                MessageDTO(
                    role=msg["role"],
                    content=msg.get("content", ""),
                    name=msg.get("name"),
                    tool_call_id=msg.get("tool_call_id"),
                )
            )
        return messages

    async def conversation_owned_by_store(self, conversation_id: str, store_id: str) -> bool:
        """
        Whether the conversation belongs to the given store.

        - Unknown conversation → True (a fresh conversation may be started).
        - Legacy conversation without store tagging → False (not resumable via widget).
        - Otherwise the store must match.
        """
        owner = await self.repository.owner_store_id(conversation_id)
        if owner is None:
            return True
        return owner == store_id

    async def save_interaction(
        self,
        conversation_id: str,
        user_message: MessageDTO,
        assistant_message: MessageDTO,
        usage: UsageDTO | None = None,
        latency_ms: float | None = None,
        store_id: str | None = None,
    ) -> None:
        """
        Persists both the user prompt and assistant response to conversation history.
        """
        # Save user message
        user_dict = {
            "role": user_message.role,
            "content": user_message.content,
            "name": user_message.name,
        }
        await self.repository.add_message(conversation_id, user_dict, store_id=store_id)

        # Save assistant message and update stats
        assistant_dict = {
            "role": assistant_message.role,
            "content": assistant_message.content,
            "name": assistant_message.name,
        }
        if assistant_message.tool_calls:
            assistant_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function_name": tc.function_name,
                    "arguments": tc.arguments,
                }
                for tc in assistant_message.tool_calls
            ]

        usage_dict = None
        if usage:
            usage_dict = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost": usage.cost,
            }

        await self.repository.add_message(
            conversation_id,
            assistant_dict,
            usage=usage_dict,
            latency_ms=latency_ms,
            store_id=store_id,
        )
