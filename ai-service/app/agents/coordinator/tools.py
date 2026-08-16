import json
import logging
from typing import Any

from app.application.contracts.intent import (
    COMING_SOON_INTENTS as CANONICAL_COMING_SOON_INTENTS,
)
from app.application.contracts.intent import EXECUTABLE_INTENTS as CANONICAL_EXECUTABLE_INTENTS
from app.application.contracts.intent import Intent
from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.core.ai_settings import ai_settings
from app.infrastructure.prompts.client import get_prompt_client
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

VALID_INTENTS = {intent.value for intent in Intent}

# Intents the coordinator can hand off to an executable conversational agent.
EXECUTABLE_INTENTS = {intent.value for intent in CANONICAL_EXECUTABLE_INTENTS}

# Intents that exist in the routing table but have no executable agent yet.
COMING_SOON_INTENTS = {intent.value for intent in CANONICAL_COMING_SOON_INTENTS}


def _get_llm() -> BaseLLMProvider:
    return LLMProviderFactory().get_provider("openrouter")


def available_agents() -> list[dict[str, Any]]:
    """Routing table of available agents and their capabilities."""
    return [
        {"name": "bundle", "description": "Bundle deals, multi-product discounts, promo codes", "status": "available"},
        {"name": "recommendation", "description": "Product suggestions and buying advice", "status": "available"},
        {"name": "integration", "description": "API connections and platform integration", "status": "available"},
        {"name": "sales", "description": "Conversational sales funnel", "status": "available"},
        {"name": "support", "description": "Customer issue resolution", "status": "available"},
        {"name": "escalation", "description": "Human handoff for critical issues", "status": "available"},
        {"name": "marketing", "description": "Campaign creation and management", "status": "coming_soon"},
        {"name": "analytics", "description": "Natural-language business intelligence", "status": "coming_soon"},
    ]


async def classify_intent(
    user_input: str,
    history: str = "",
    llm: BaseLLMProvider | None = None,
) -> tuple[str, float]:
    """Classify user input into an intent and return (intent, confidence)."""
    provider = llm or _get_llm()
    prompt = await get_prompt_client().get("coordinator.intent_classification_prompt")
    request = ChatRequest(
        messages=[
            MessageDTO(
                role="system",
                content="You classify e-commerce user messages into intents. Return only valid JSON.",
            ),
            MessageDTO(
                role="user",
                content=prompt.format(user_input=user_input, history=history),
            ),
        ],
        model=ai_settings.DEFAULT_MODEL,
        json_mode=True,
    )
    response = await provider.structured_output(request, dict[str, Any])
    data = json.loads(response.message.content)

    intent = data.get("intent", "general")
    if intent not in VALID_INTENTS:
        intent = "general"
    confidence = float(data.get("confidence", 0.5))
    return intent, max(0.0, min(1.0, confidence))


async def extract_context(
    user_input: str,
    history: str = "",
    store_profile: dict[str, Any] | None = None,
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    """Extract relevant context from the user input, history, and store profile."""
    provider = llm or _get_llm()
    prompt = await get_prompt_client().get("coordinator.context_extraction_prompt")
    request = ChatRequest(
        messages=[
            MessageDTO(
                role="system",
                content="You extract structured context from e-commerce conversations. Return only valid JSON.",
            ),
            MessageDTO(
                role="user",
                content=prompt.format(
                    user_input=user_input,
                    history=history,
                    store_profile=json.dumps(store_profile or {}),
                ),
            ),
        ],
        model=ai_settings.DEFAULT_MODEL,
        json_mode=True,
    )
    response = await provider.structured_output(request, dict[str, Any])
    data = json.loads(response.message.content)
    return {
        "key_topics": data.get("key_topics", []),
        "customer_preferences": data.get("customer_preferences", []),
        "store_facts": data.get("store_facts", []),
        "sentiment": data.get("sentiment", "neutral"),
    }


async def build_fallback_response(
    user_input: str,
    intent: str | None,
    llm: BaseLLMProvider | None = None,
) -> str:
    """Build a graceful fallback (clarifying question) response."""
    provider = llm or _get_llm()
    if intent in COMING_SOON_INTENTS:
        prompt_template = await get_prompt_client().get("coordinator.coming_soon_prompt")
    else:
        prompt_template = await get_prompt_client().get("coordinator.fallback_prompt")

    request = ChatRequest(
        messages=[
            MessageDTO(role="system", content="You are a helpful e-commerce assistant."),
            MessageDTO(
                role="user",
                content=prompt_template.format(
                    user_input=user_input,
                    intent=intent or "general",
                    capabilities=json.dumps(available_agents()),
                ),
            ),
        ],
        model=ai_settings.DEFAULT_MODEL,
    )
    response = await provider.chat(request)
    return response.message.content


def format_history(messages: list[dict[str, Any]]) -> str:
    """Format conversation messages into a compact history string."""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        parts.append(f"{role}: {content}")
    return "\n".join(parts)
