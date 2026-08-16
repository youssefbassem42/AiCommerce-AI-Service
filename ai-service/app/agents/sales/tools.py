import json
import logging
from typing import Any

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.core.ai_settings import ai_settings
from app.infrastructure.prompts.client import get_prompt_client
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


async def extract_needs(
    query: str,
    llm: BaseLLMProvider,
    current_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract budget/use case/preferences. Returns needs dict + clarifying question.

    ``current_state`` carries already-known shopping context so the extractor
    does not re-ask answered questions across turns.
    """
    default = {
        "budget": None,
        "use_case": None,
        "preferences": [],
        "has_enough_info": False,
        "clarifying_question": None,
    }
    try:
        prompt = await get_prompt_client().get("sales.needs_extraction_prompt")
        content = prompt.format(query=query)
        if current_state:
            known = {k: v for k, v in current_state.items() if v}
            if known:
                content += "\n\nAlready known about this shopper:\n" + str(known)
        request = ChatRequest(
            messages=[
                MessageDTO(
                    role="system",
                    content="You extract shopping context from user messages. Return only valid JSON.",
                ),
                MessageDTO(role="user", content=content),
            ],
            model=ai_settings.DEFAULT_MODEL,
            json_mode=True,
        )
        response = await llm.structured_output(request, dict[str, Any])
        data = json.loads(response.message.content)
        if isinstance(data, dict):
            merged = {**default, **data}
            if current_state and not merged.get("has_enough_info"):
                merged["has_enough_info"] = bool(
                    current_state.get("budget") or current_state.get("use_case") or current_state.get("preferences")
                )
            return merged
    except Exception as exc:
        logger.error("Needs extraction failed: %s", exc, exc_info=True)
    return default


async def detect_objection(query: str, llm: BaseLLMProvider) -> dict[str, Any]:
    """Detect an objection and build a tailored rebuttal."""
    default = {"objection_detected": False, "objection_type": None, "rebuttal": None}
    try:
        prompt = await get_prompt_client().get("sales.objection_prompt")
        request = ChatRequest(
            messages=[
                MessageDTO(
                    role="system",
                    content="You detect sales objections. Return only valid JSON.",
                ),
                MessageDTO(role="user", content=prompt.format(query=query)),
            ],
            model=ai_settings.DEFAULT_MODEL,
            json_mode=True,
        )
        response = await llm.structured_output(request, dict[str, Any])
        data = json.loads(response.message.content)
        if isinstance(data, dict):
            return {**default, **data}
    except Exception as exc:
        logger.error("Objection detection failed: %s", exc, exc_info=True)
    return default


async def build_offer_payload(
    query: str,
    products: list[Any],
    llm: BaseLLMProvider,
) -> dict[str, Any]:
    """Build a structured offer (primary, cross-sell, upsell, discount, message)."""
    products_text = "\n".join(f"- {p.product_id}: {p.title} ({p.price} {p.currency})" for p in products)
    default = {
        "primary": None,
        "cross_sell": None,
        "upsell": None,
        "discount_pct": 10.0,
        "message": None,
    }
    try:
        prompt = await get_prompt_client().get("sales.offer_prompt")
        request = ChatRequest(
            messages=[
                MessageDTO(
                    role="system",
                    content="You build personalized sales offers. Return only valid JSON.",
                ),
                MessageDTO(role="user", content=prompt.format(products=products_text, query=query)),
            ],
            model=ai_settings.DEFAULT_MODEL,
            json_mode=True,
        )
        response = await llm.structured_output(request, dict[str, Any])
        data = json.loads(response.message.content)
        if isinstance(data, dict):
            return {**default, **data}
    except Exception as exc:
        logger.error("Offer building failed: %s", exc, exc_info=True)
        if products:
            default["primary"] = products[0].product_id
            default["message"] = f"I'd recommend the {products[0].title} as your best match."
    return default
