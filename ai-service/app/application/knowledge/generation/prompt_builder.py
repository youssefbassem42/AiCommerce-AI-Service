import json

from app.infrastructure.prompts.client import get_prompt_client


async def get_section_definitions() -> dict[str, str]:
    raw = await get_prompt_client().get("knowledge.generation.section_definitions")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except json.JSONDecodeError:
        pass
    return {}


async def build_generation_messages(merged_content: str) -> list[dict]:
    client = get_prompt_client()
    system_prompt = await client.get("knowledge.generation.system_prompt")
    section_definitions = await get_section_definitions()
    user_content = (
        "Generate a complete business context from the following documents.\n\n"
        "Return a JSON object with exactly these keys, each containing the generated text:\n"
        + "\n".join(f'  "{key}": "{desc}"' for key, desc in section_definitions.items())
        + '\n\nAlso include a key "rag_context" that contains a single optimized text combining all sections '
        "into a concise, searchable business context suitable for a RAG system. "
        "The rag_context should be a narrative text, not JSON.\n\n"
        "Documents:\n\n"
        f"{merged_content}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
