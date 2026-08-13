import json
import logging
from decimal import Decimal
from typing import Any

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.application.knowledge.retrieval.service import RetrieverService
from app.application.recommendation.dto.recommendation_dto import (
    ProductCard,
    ProductSpecValue,
    RecommendationIntent,
    ScoredProduct,
)
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)


def _get_llm() -> BaseLLMProvider:
    from app.core.ai_settings import ai_settings

    provider_name = ai_settings.DEFAULT_PROVIDER
    try:
        return LLMProviderFactory().get_provider(provider_name)
    except Exception:
        return LLMProviderFactory().get_provider("openai")


INTENT_EXTRACTION_PROMPT = """You are a product recommendation intent parser.
Extract structured information about what the user wants to buy.

User query: {query}

Return a JSON object with these fields:
- product_type: what they want to buy (e.g., "laptop", "phone stand", "monitor") or null if unclear
- use_case: how they will use it (e.g., "gaming", "cooking", "office work") or null if unclear
- required_specs: list of specific requirements as {{"spec_name": "required_value"}} objects (e.g., {{"ram": ">= 16GB"}}, {{"color": "black"}})
- max_budget: maximum budget as a number if mentioned, otherwise null
- min_quality: quality tier ("premium", "budget", "mid-range") or null
- hidden_needs: list of inferred needs not explicitly stated but implied by the use case

Only return valid JSON. No markdown, no explanation."""


async def parse_intent(query: str, llm: BaseLLMProvider | None = None) -> RecommendationIntent:
    provider = llm or _get_llm()
    request = ChatRequest(
        messages=[
            MessageDTO(
                role="system",
                content="You extract structured recommendation intent from user queries. Return only valid JSON.",
            ),
            MessageDTO(role="user", content=INTENT_EXTRACTION_PROMPT.format(query=query)),
        ],
        model="gpt-4o-mini",
        json_mode=True,
    )
    response = await provider.structured_output(request, RecommendationIntent)
    data = json.loads(response.message.content)
    return RecommendationIntent(**data)


async def search_spec_vectors(
    intent: RecommendationIntent,
    retriever_service: RetrieverService,
    store_id: str,
    top_k: int = 20,
) -> list[ScoredProduct]:
    if not intent.product_type and not intent.use_case and not intent.required_specs:
        return []

    search_terms = [intent.product_type, intent.use_case] + intent.hidden_needs
    query_text = " ".join(t for t in search_terms if t)

    if intent.required_specs:
        spec_text = " ".join(f"{list(s.keys())[0]} {list(s.values())[0]}" for s in intent.required_specs)
        query_text = f"{query_text} {spec_text}"

    if not query_text.strip():
        return []

    filters = RetrievalFilters(store_id=store_id)
    config = RetrievalConfig(top_k=top_k, use_hybrid=True)

    result = await retriever_service.search(query=query_text, filters=filters, config=config)
    if not result.results:
        return []

    products = []
    for chunk in result.results:
        payload = chunk.metadata or {}
        price = payload.get("price")
        price_decimal = Decimal(str(price)) if isinstance(price, (int, float)) else Decimal("0")
        specs = [
            ProductSpecValue(name=str(s.get("name", "")), value=str(s.get("value", "")))
            for s in (payload.get("specs") or [])
            if isinstance(s, dict)
        ]
        products.append(
            ScoredProduct(
                product_id=payload.get("product_id", chunk.chunk_id),
                store_id=store_id,
                title=payload.get("product_title", payload.get("document_title", "Unknown Product")),
                description=payload.get("content", "")[:200],
                price=price_decimal,
                currency=payload.get("currency", "USD"),
                image_url=payload.get("image_url"),
                product_url=payload.get("product_url"),
                specs=specs,
                match_score=chunk.score,
                match_reasons=[f"Spec match: {chunk.score:.2f}"],
                score=chunk.score,
            )
        )

    products.sort(key=lambda p: p.score, reverse=True)
    return products[:top_k]


def _product_in_stock(product: Any) -> bool:
    if product is None:
        return False
    variants = list(product.variants or [])
    if variants:
        return any(v.inventory_quantity > 0 for v in variants)
    return int(getattr(product, "inventory_quantity", 0) or 0) > 0


def _product_prices(product: Any) -> list[float]:
    """Min candidate prices from variants, falling back to the flat-schema price."""
    if product is None:
        return []
    variants = list(product.variants or [])
    prices = [float(v.price.amount) for v in variants if v.price is not None]
    if prices:
        return prices
    flat = getattr(product, "price", None)
    if flat is not None:
        try:
            return [float(flat.amount)]
        except (AttributeError, TypeError, ValueError):
            try:
                return [float(flat)]
            except (TypeError, ValueError):
                return []
    return []


async def filter_inventory(
    candidates: list[ScoredProduct],
    product_repo: ProductRepository,
) -> list[ScoredProduct]:
    if not candidates:
        return []

    filtered = []
    for candidate in candidates:
        try:
            product = await product_repo.find_by_id(candidate.product_id)
            variants_in_stock = _product_in_stock(product)

            candidate.in_stock = variants_in_stock
            if variants_in_stock:
                filtered.append(candidate)
        except Exception:
            logger.warning("Failed to check inventory for product %s", candidate.product_id)
            continue

    return filtered


async def apply_budget_filter(
    candidates: list[ScoredProduct],
    max_budget: float | None,
    product_repo: ProductRepository,
) -> list[ScoredProduct]:
    if max_budget is None:
        return candidates

    filtered = []
    for candidate in candidates:
        try:
            product = await product_repo.find_by_id(candidate.product_id)
            if product is None:
                continue
            prices = _product_prices(product)
            if prices:
                min_price = min(prices)
                if min_price <= max_budget:
                    candidate.price = min_price
                    filtered.append(candidate)
        except Exception:
            logger.warning("Failed to check price for product %s", candidate.product_id)
            continue

    return filtered


def build_product_cards(products: list[ScoredProduct], reason: str = "") -> list[ProductCard]:
    cards = []
    for p in products:
        cards.append(
            ProductCard(
                product_id=p.product_id,
                title=p.title,
                price=p.price,
                currency=p.currency,
                image_url=p.image_url,
                product_url=p.product_url,
                specs=p.specs,
                match_reasons=p.match_reasons,
            )
        )
    return cards
