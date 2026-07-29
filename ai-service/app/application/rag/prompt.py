RAG_SYSTEM_PROMPT = """You are a knowledgeable AI commerce assistant. Your answers must be grounded in the provided context.

## Core Rules
1. Answer ONLY using the context below. If the context lacks the information, say "I don't have enough information to answer that."
2. Always cite your sources using the format [citation:N] where N is the chunk number.
3. When referencing business policies or guidelines, also cite the relevant business summary context.
4. Be concise, accurate, and helpful. Do not make up facts.

## Context"""

BUSINESS_SUMMARY_HEADER = "\n\n### Business Context (v{version})\n{summary}"

CHUNK_HEADER = "\n\n### Retrieved Knowledge Chunk [{index}]\n**Source:** {title}\n{content}"

USER_MESSAGE_TEMPLATE = "{message}"

CONTEXT_PLACEHOLDER = (
    "\n\n---\nNote: If you cannot answer based on the provided context, "
    "clearly state that. Do not speculate."
)


def build_rag_messages(
    user_message: str,
    chunks_context: str,
    business_summary_context: str | None = None,
    business_summary_version: int | None = None,
    conversation_history: list | None = None,
) -> tuple[str, str, str]:
    system_parts = [RAG_SYSTEM_PROMPT]

    if business_summary_context and business_summary_version:
        system_parts.append(
            BUSINESS_SUMMARY_HEADER.format(
                version=business_summary_version,
                summary=business_summary_context,
            )
        )

    system_parts.append(chunks_context)
    system_parts.append(CONTEXT_PLACEHOLDER)
    system_content = "\n".join(system_parts)

    return system_content, user_message, RAG_SYSTEM_PROMPT
