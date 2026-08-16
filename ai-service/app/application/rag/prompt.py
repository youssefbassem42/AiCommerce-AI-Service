from app.infrastructure.prompts.client import get_prompt_client


async def build_rag_messages(
    user_message: str,
    chunks_context: str,
    business_summary_context: str | None = None,
    business_summary_version: int | None = None,
    conversation_history: list | None = None,
) -> tuple[str, str, str]:
    client = get_prompt_client()
    system_prompt = await client.get("rag.core.system_prompt")
    summary_header = await client.get("rag.core.business_summary_header")
    context_placeholder = await client.get("rag.core.context_placeholder")

    system_parts = [system_prompt]

    if business_summary_context and business_summary_version:
        system_parts.append(
            summary_header.format(
                version=business_summary_version,
                summary=business_summary_context,
            )
        )

    system_parts.append(chunks_context)
    system_parts.append(context_placeholder)
    system_content = "\n".join(system_parts)

    return system_content, user_message, system_prompt
