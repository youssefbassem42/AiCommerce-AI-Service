import logging
from typing import Any

from app.agents.sales.state import SalesState
from app.agents.sales.tools import build_offer_payload, detect_objection, extract_needs
from app.application.context.shopping_state import SESSION_STATE_KEY, shopping_state_from_context
from app.application.recommendation.dto.sales_dto import SalesResponse
from app.application.recommendation.promo_service import PromoCodeService
from app.application.recommendation.services import RecommendationService
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

SALES_DISCOUNT_DEFAULT = 10.0
SALES_PROMO_PREFIX = "SALES"


async def discover_needs_node(
    state: SalesState,
    llm: BaseLLMProvider,
) -> dict[str, Any]:
    try:
        shopping = shopping_state_from_context(state.get("context") or {})
        needs = await extract_needs(
            state["user_query"],
            llm=llm,
            current_state=shopping.to_dict() if not shopping.is_empty() else None,
        )
        answers = {
            "budget": needs.get("budget"),
            "use_case": needs.get("use_case"),
            "preferences": needs.get("preferences", []),
        }
        if not needs.get("has_enough_info"):
            return {
                "stage": "discovery",
                "customer_answers": answers,
                "clarifying_question": needs.get("clarifying_question")
                or "Could you tell me your budget and what you're looking for?",
                "error": None,
            }
        return {"stage": "qualification", "customer_answers": answers, "error": None}
    except Exception as exc:
        logger.error("Discovery failed: %s", exc, exc_info=True)
        return {
            "stage": "discovery",
            "customer_answers": {},
            "clarifying_question": "Could you tell me more about what you're looking for?",
            "error": f"Discovery failed: {exc}",
        }


async def recommend_products_node(
    state: SalesState,
    recommendation_service: RecommendationService,
) -> dict[str, Any]:
    if state.get("error"):
        return {"products": []}

    try:
        context = _merge_sales_answers(state)
        result = await recommendation_service.recommend(
            query=state["user_query"],
            store_id=state["store_id"],
            customer_id=state.get("customer_id"),
            context=context,
        )
        products = list(result.products)
        return {"stage": "recommendation", "products": products, "error": None}
    except Exception as exc:
        logger.error("Recommendation failed: %s", exc, exc_info=True)
        return {"stage": "recommendation", "products": [], "error": f"Recommendation failed: {exc}"}


def _merge_sales_answers(state: SalesState) -> dict[str, Any]:
    """Merge the sales-discovered needs into the shared shopping state.

    The recommendation service reads the shopping state from the context dict,
    so qualifying answers collected by the sales agent must be merged back into
    ``context.conversation.shopping_state`` before recommending (Fix: sales
    never loses the customer_answers it gathered).
    """
    context = dict(state.get("context") or {})
    shopping = shopping_state_from_context(context)
    merged = shopping.merge(state.get("customer_answers") or {})
    if not merged.is_empty():
        conversation = dict(context.get("conversation") or {})
        conversation[SESSION_STATE_KEY] = merged.to_dict()
        context["conversation"] = conversation
    return context


async def handle_objection_node(
    state: SalesState,
    llm: BaseLLMProvider,
) -> dict[str, Any]:
    try:
        result = await detect_objection(state["user_query"], llm=llm)
        if result.get("objection_detected"):
            return {
                "stage": "objection_handling",
                "objection": result,
                "error": None,
            }
    except Exception as exc:
        logger.error("Objection handling failed: %s", exc, exc_info=True)
    return {"stage": "close", "objection": None, "error": None}


async def build_offer_node(
    state: SalesState,
    llm: BaseLLMProvider,
) -> dict[str, Any]:
    products = state.get("products", [])
    if not products:
        return {"stage": "close", "offer": {}, "error": None}

    try:
        offer = await build_offer_payload(state["user_query"], products, llm=llm)
        return {"stage": "close", "offer": offer, "error": None}
    except Exception as exc:
        logger.error("Offer building failed: %s", exc, exc_info=True)
        return {"stage": "close", "offer": {}, "error": None}


async def close_sale_node(
    state: SalesState,
    promo_service: PromoCodeService | None = None,
) -> dict[str, Any]:
    products = state.get("products", [])
    offer = state.get("offer") or {}
    if not products:
        return {"stage": "close", "promo_code": None, "error": None}

    capabilities = state.get("store_capabilities") or {}
    promo_code = None
    checkout_note = None

    if capabilities.get("has_promo_codes", False) and promo_service:
        product_ids = [p.product_id for p in products]
        discount_pct = float(offer.get("discount_pct") or SALES_DISCOUNT_DEFAULT)
        try:
            promo_code = await promo_service.generate_code(
                store_id=state["store_id"],
                product_ids=product_ids,
                discount_pct=discount_pct,
                prefix=SALES_PROMO_PREFIX,
            )
            if promo_code:
                checkout_note = f"Use promo code {promo_code} at checkout for {discount_pct:.0f}% off these items."
            else:
                checkout_note = "Your items are ready to check out. Ask your store about current discounts."
        except Exception as exc:
            logger.error("Promo code generation failed: %s", exc, exc_info=True)
            checkout_note = "Your items are ready to check out. Ask your store about current discounts."
    else:
        checkout_note = "Your items are ready to check out. Select them in the cart to complete your purchase."

    return {
        "stage": "close",
        "promo_code": promo_code,
        "checkout_note": checkout_note,
        "error": None,
    }


async def format_sales_response_node(state: SalesState) -> dict[str, Any]:
    products = state.get("products", [])
    offer = state.get("offer") or {}
    objection = state.get("objection")
    stage = state.get("stage") or "discovery"

    if state.get("clarifying_question") or stage == "discovery":
        rationale = state.get("clarifying_question") or "Let's find the perfect products for you."
    elif objection and objection.get("objection_detected"):
        rationale = objection.get("rebuttal") or ("Let me address that concern and find a better option for you.")
    else:
        message = offer.get("message")
        note = state.get("checkout_note")
        parts = []
        if message:
            parts.append(message)
        if note:
            parts.append(note)
        rationale = (
            " ".join(parts) if parts else ("Here are the best matches for you — ready to check out whenever you are.")
        )

    response = SalesResponse(
        query=state.get("user_query", ""),
        store_id=state.get("store_id", ""),
        customer_id=state.get("customer_id"),
        stage=stage,
        products=products,
        offer=offer,
        objection=objection,
        promo_code=state.get("promo_code"),
        checkout_note=state.get("checkout_note"),
        clarifying_question=state.get("clarifying_question"),
        rationale=rationale,
    )
    return {"response": response}
