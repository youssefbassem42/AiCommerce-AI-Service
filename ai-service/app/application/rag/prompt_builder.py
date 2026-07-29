import logging
from typing import Any, Optional

from app.application.dto.ai_dto import MessageDTO
from app.application.rag.context_builder import BuiltContext
from app.application.rag.prompt import (
    BUSINESS_SUMMARY_HEADER,
    CHUNK_HEADER,
    CONTEXT_PLACEHOLDER,
    RAG_SYSTEM_PROMPT,
    build_rag_messages,
)

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 2000
MAX_CHUNKS_IN_CONTEXT = 10

DEVELOPER_PROMPT = (
    "You are a helpful, accurate commerce assistant. "
    "Answer the user's question using ONLY the business summary and "
    "retrieved knowledge chunks provided below. "
    "If you cannot find the answer in the provided context, "
    "say 'I don't have enough information to answer that.' "
    "Do not make up facts or speculate."
)


class PromptBuilder:
    """Assembles the final LLM prompt from tenant-aware RAG context.

    Reuses existing prompt templates from app.application.rag.prompt.
    Always sends the final prompt via ChatService — never calls providers directly.
    """

    def __init__(
        self,
        developer_prompt: str = DEVELOPER_PROMPT,
        max_chunk_chars: int = MAX_CHUNK_CHARS,
        max_chunks: int = MAX_CHUNKS_IN_CONTEXT,
    ) -> None:
        self._developer_prompt = developer_prompt
        self._max_chunk_chars = max_chunk_chars
        self._max_chunks = max_chunks

    def build(
        self,
        user_message: str,
        context: BuiltContext,
        conversation_history: Optional[list[MessageDTO]] = None,
    ) -> list[MessageDTO]:
        system_content = self._build_system_content(context)
        user_content = self._build_user_content(user_message, context)

        messages: list[MessageDTO] = [MessageDTO(role="system", content=system_content)]

        if conversation_history:
            messages.extend(self._truncate_history(conversation_history))

        messages.append(MessageDTO(role="user", content=user_content))
        return messages

    def build_single_prompt(
        self,
        user_message: str,
        context: BuiltContext,
        conversation_history: Optional[list[MessageDTO]] = None,
    ) -> str:
        """Build a single final prompt string (no separate system/user messages)."""
        parts: list[str] = []

        parts.append(f"# System\n{self._developer_prompt}")
        parts.append(f"# Business Summary\n{context.business_summary or '(none)'}")
        parts.append(f"# Retrieved Context\n{self._format_chunks(context.chunks)}")

        if conversation_history:
            history_str = "\n".join(
                f"{m.role}: {m.content}" for m in conversation_history[-6:]
            )
            parts.append(f"# Conversation History\n{history_str}")

        parts.append(f"# User\n{user_message}")
        parts.append(CONTEXT_PLACEHOLDER.strip())
        return "\n\n".join(parts)

    def _build_system_content(self, context: BuiltContext) -> str:
        system_parts = [RAG_SYSTEM_PROMPT]

        if context.business_summary and context.business_summary_version:
            system_parts.append(
                BUSINESS_SUMMARY_HEADER.format(
                    version=context.business_summary_version,
                    summary=context.business_summary,
                )
            )

        system_parts.append(self._format_chunks(context.chunks))
        system_parts.append(CONTEXT_PLACEHOLDER)
        return "\n".join(system_parts)

    def _build_user_content(self, message: str, context: BuiltContext) -> str:
        return message

    def _format_chunks(self, chunks: list) -> str:
        lines: list[str] = []
        for i, c in enumerate(chunks[:self._max_chunks]):
            snippet = (c.content or "")[:self._max_chunk_chars]
            lines.append(
                CHUNK_HEADER.format(index=i + 1, title=c.document_title)
                + "\n"
                + snippet
            )
        return "\n".join(lines)

    @staticmethod
    def _truncate_history(history: list[MessageDTO], max_pairs: int = 6) -> list[MessageDTO]:
        return history[-max_pairs:]
