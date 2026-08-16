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
from app.core.ai_settings import ai_settings
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.shared.vector_payloads import EntityType

logger = logging.getLogger(__name__)


def _get_llm() -> BaseLLMProvider:
    provider_name = ai_settings.DEFAULT_PROVIDER
    try:
        return LLMProviderFactory().get_provider(provider_name)
    except Exception:
        return LLMProviderFactory().get_provider("openai")


INTENT_EXTRACTION_PROMPT = """You are a product recommendation intent parser.
Extract structured information about what the user wants to buy.

Known requirements from the ongoing conversation (already gathered):
{known_requirements}

If the known requirements already answer a field, leave that field null in
your output — only report what the CURRENT message adds or clarifies.

Current user message: {query}

Return a JSON object with these fields (Fix 4.1):
- category: what they want to buy (e.g., "laptop", "phone stand", "monitor") or null if unclear
- budget: maximum budget as a number if mentioned in the CURRENT message, otherwise null
- currency: 3-letter currency code (e.g., "USD") if mentioned, otherwise null
- use_case: how they will use it (e.g., "gaming", "cooking", "office work") or null if unclear
- brand: preferred brand if stated, otherwise null
- attributes: object of specific requirements as {{"attribute": "required value"}} (e.g., {{"ram": ">= 16GB"}}, {{"color": "black"}}) mentioned in the CURRENT message
- required_specs: list of the same specific requirements as [{{"name": "value"}}] objects (e.g., [{{"ram": ">= 16GB"}}])
- min_quality: quality tier ("premium", "budget", "mid-range") or null
- hidden_needs: list of inferred needs not explicitly stated but implied by the use case

Only return valid JSON. No markdown, no explanation."""


async def parse_intent(
    query: str,
    llm: BaseLLMProvider | None = None,
    shopping_state: dict[str, Any] | None = None,
) -> RecommendationIntent:
    provider = llm or _get_llm()
    request = ChatRequest(
        messages=[
            MessageDTO(
                role="system",
                content="You extract structured recommendation intent from user queries. Return only valid JSON.",
            ),
            MessageDTO(
                role="user",
                content=INTENT_EXTRACTION_PROMPT.format(
                    query=query,
                    known_requirements=_format_known_requirements(shopping_state),
                ),
            ),
        ],
        model=ai_settings.DEFAULT_MODEL,
        json_mode=True,
    )
    response = await provider.structured_output(request, RecommendationIntent)
    data = json.loads(response.message.content)
    parsed = RecommendationIntent(**data)
    return normalize_intent(apply_shopping_state(parsed, shopping_state))


def _spec_name_value(spec: dict[str, str] | None) -> tuple[str | None, str | None]:
    """Read a requirement from either supported shape (legacy and canonical)."""
    if not spec:
        return None, None
    if "name" in spec:
        return spec.get("name"), spec.get("value")
    name, value = next(iter(spec.items()))
    return name, value


def normalize_intent(intent: RecommendationIntent) -> RecommendationIntent:
    """Normalize a parsed intent into the canonical structured request (Fix 4.1).

    - Synchronizes `attributes` (dict) with `required_specs` (list) so both
      views of the same explicit requirements agree.
    - Defaults the currency when neither the message nor the conversation
      state provided one.
    """
    spec_dict = {
        str(name).lower(): str(value)
        for name, value in (_spec_name_value(spec) for spec in intent.required_specs)
        if name and value is not None
    }
    for name, value in (intent.attributes or {}).items():
        if value is not None and str(name).lower() not in spec_dict:
            spec_dict[str(name).lower()] = str(value)
    intent.required_specs = [{"name": name, "value": value} for name, value in spec_dict.items()]
    intent.attributes = dict(spec_dict)

    if not intent.currency:
        intent.currency = "USD"
    return intent


def _format_known_requirements(shopping_state: dict[str, Any] | None) -> str:
    """Render recalled conversation constraints for the intent parser."""
    if not shopping_state:
        return "(none yet)"
    from app.application.context.shopping_state import ShoppingState

    return ShoppingState.from_dict(shopping_state).to_prompt_text() or "(none yet)"


def apply_shopping_state(
    intent: RecommendationIntent,
    shopping_state: dict[str, Any] | None,
) -> RecommendationIntent:
    """Merge recalled conversation state into the parsed intent.

    The current message wins per field; the recalled state fills any gaps so
    multi-turn requirements (category, budget, use case, color, ...) reach
    the search without the user repeating them (Fix 3.5).
    """
    if not shopping_state:
        return intent
    from app.application.context.shopping_state import ShoppingState

    state = ShoppingState.from_dict(shopping_state)

    product_type = intent.product_type or state.category
    if product_type:
        intent.product_type = product_type

    if intent.max_budget is None and state.budget is not None:
        intent.max_budget = state.budget

    if not intent.use_case and state.use_case:
        intent.use_case = state.use_case

    if not intent.currency and state.currency:
        intent.currency = state.currency

    if not intent.brand and state.brand:
        intent.brand = state.brand

    spec_values = {
        str(name).lower(): str(value)
        for name, value in (_spec_name_value(spec) for spec in intent.required_specs)
        if name and value is not None
    }
    merged_specs = list(intent.required_specs)
    for name, value in (
        ("color", state.color),
        ("size", state.size),
    ):
        if value and name not in spec_values:
            merged_specs.append({name: value})
    intent.required_specs = merged_specs

    return intent


async def search_spec_vectors(
    intent: RecommendationIntent,
    retriever_service: RetrieverService,
    store_id: str,
    top_k: int = 20,
) -> list[ScoredProduct]:
    if not intent.product_type and not intent.use_case and not intent.required_specs:
        return []

    search_terms = [intent.product_type, intent.use_case, intent.brand] + intent.hidden_needs
    query_text = " ".join(t for t in search_terms if t)

    if intent.required_specs:
        spec_text = " ".join(
            f"{name} {value}" for name, value in (_spec_name_value(spec) for spec in intent.required_specs) if name
        )
        query_text = f"{query_text} {spec_text}"

    if intent.attributes:
        attr_text = " ".join(f"{name} {value}" for name, value in intent.attributes.items())
        query_text = f"{query_text} {attr_text}"

    if not query_text.strip():
        return []

    filters = RetrievalFilters(store_id=store_id, entity_type=EntityType.PRODUCT.value)
    config = RetrievalConfig(top_k=top_k, use_hybrid=True)

    result = await retriever_service.search(query=query_text, filters=filters, config=config)
    if not result.results:
        return []

    products = []
    for chunk in result.results:
        payload = chunk.metadata or {}
        if payload.get("entity_type") != EntityType.PRODUCT.value:
            logger.debug(
                "Skipping candidate '%s': payload entity_type='%s' is not 'product'",
                chunk.chunk_id,
                payload.get("entity_type"),
            )
            continue
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


def _product_currency(product: Any) -> str | None:
    if product is None:
        return None
    variants = list(product.variants or [])
    if variants:
        for v in variants:
            if v.price is not None:
                return v.price.currency
        return None
    flat = getattr(product, "price", None)
    if flat is not None:
        try:
            return flat.currency
        except AttributeError:
            return None
    return None


def _catalog_price(product: Any) -> float | None:
    """Real catalog entry price; None when the product has no usable price."""
    prices = _product_prices(product)
    if not prices:
        return None
    min_price = min(prices)
    if min_price <= 0:
        return None
    return min_price


def _resolve_catalog_candidate(
    candidate: ScoredProduct,
    product: Any,
    store_id: str,
) -> ScoredProduct | None:
    """Enrich a candidate from the real catalog record.

    Returns None when the candidate cannot be resolved to a real, priced
    product of the requesting store. Payload-derived fields (title, price)
    are never trusted — the Mongo catalog is authoritative, and a product
    belonging to another store is never surfaced (tenant isolation).
    """
    if product is None:
        logger.debug("Discarding candidate '%s': no catalog product", candidate.product_id)
        return None

    if getattr(product, "store_id", None) != store_id:
        logger.debug(
            "Discarding candidate '%s': catalog product belongs to store '%s', not '%s'",
            candidate.product_id,
            getattr(product, "store_id", None),
            store_id,
        )
        return None

    price = _catalog_price(product)
    if price is None:
        logger.debug("Discarding candidate '%s': no real catalog price", candidate.product_id)
        return None

    candidate.price = Decimal(str(price))
    candidate.price_resolved = True
    currency = _product_currency(product)
    if currency:
        candidate.currency = currency
    title = getattr(product, "title", None)
    if title:
        candidate.title = title
    images = list(getattr(product, "images", None) or [])
    if images and images[0].url:
        candidate.image_url = images[0].url
    handle = getattr(product, "handle", None)
    if handle:
        candidate.product_url = handle
    metadata = getattr(product, "metadata", None) or {}
    try:
        candidate.max_discount_pct = float(metadata.get("max_discount_pct", 0.0) or 0.0)
    except (TypeError, ValueError):
        candidate.max_discount_pct = 0.0
    candidate.stock_quantity = _catalog_stock_quantity(product)
    return candidate


def _catalog_stock_quantity(product: Any) -> int:
    variants = list(getattr(product, "variants", None) or [])
    if variants:
        return sum(int(v.inventory_quantity or 0) for v in variants)
    return int(getattr(product, "inventory_quantity", 0) or 0)


async def filter_inventory(
    candidates: list[ScoredProduct],
    product_repo: ProductRepository,
    store_id: str,
) -> list[ScoredProduct]:
    """Keep only candidates that resolve to a real, in-stock catalog product.

    A vector result that cannot be resolved to a real Mongo product of the
    requesting store is discarded — never kept as a payload-derived
    "fake product".
    """
    if not candidates:
        return []

    filtered = []
    for candidate in candidates:
        if candidate.price_resolved:
            filtered.append(candidate)
            continue
        try:
            product = await product_repo.find_by_id(candidate.product_id)
        except Exception:
            logger.debug("Product lookup failed for '%s'", candidate.product_id, exc_info=True)
            product = None

        resolved = _resolve_catalog_candidate(candidate, product, store_id)
        if resolved is None:
            continue

        resolved.in_stock = _product_in_stock(product)
        if resolved.in_stock:
            filtered.append(resolved)

    return filtered


async def apply_budget_filter(
    candidates: list[ScoredProduct],
    max_budget: float | None,
    product_repo: ProductRepository,
    store_id: str,
) -> list[ScoredProduct]:
    """Keep only candidates whose real catalog price fits the budget.

    Budgets are always computed from catalog prices; payload-derived prices
    (and $0 placeholders) never enter recommendation results.

    A product above budget is still kept when its maximum allowed discount
    (Fix 4.4) brings it within budget — the discount math itself is applied
    later by the deterministic business service.
    """
    if max_budget is None:
        return candidates

    budget = Decimal(str(max_budget))
    filtered = []
    for candidate in candidates:
        if not candidate.price_resolved:
            try:
                product = await product_repo.find_by_id(candidate.product_id)
            except Exception:
                product = None
            resolved = _resolve_catalog_candidate(candidate, product, store_id)
            if resolved is None:
                continue
            candidate = resolved
        if candidate.price <= budget:
            filtered.append(candidate)
            continue
        if candidate.max_discount_pct > 0:
            final_price = (
                candidate.price * (Decimal("1") - Decimal(str(candidate.max_discount_pct)) / Decimal("100"))
            ).quantize(Decimal("0.01"))
            if final_price <= budget:
                filtered.append(candidate)
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
                discount_pct=p.discount_pct,
                discount_available=p.discount_available,
                final_price=p.final_price,
                in_stock=p.in_stock,
            )
        )
    return cards


EXPLANATION_PROMPT = """You are a commerce assistant. A deterministic engine computed this
structured recommendation result:

{structured}

Write a concise, friendly explanation for the customer (2-4 sentences):
1. Acknowledge what they asked for.
2. Present the top picks and why each fits (use the match_reasons).
3. If a discount was applied, state the original price, the discount, and the
   final price — the numbers come from the structured result, never invent prices.

Do not mention that a system computed the result. Answer in plain text, no markdown."""


async def explain_recommendation(
    structured: dict[str, Any],
    llm: BaseLLMProvider | None = None,
) -> str | None:
    """Let the LLM explain the deterministic structured result (Fix 4.5).

    Returns None when the provider is unavailable or fails, so callers fall
    back to a template rationale — explanation is presentation, never logic.
    """
    provider = llm or _get_llm()
    try:
        request = ChatRequest(
            messages=[
                MessageDTO(
                    role="system",
                    content="You explain structured recommendation results to customers. Plain text only.",
                ),
                MessageDTO(
                    role="user",
                    content=EXPLANATION_PROMPT.format(structured=json.dumps(structured, indent=2, default=str)),
                ),
            ],
            model=ai_settings.DEFAULT_MODEL,
            json_mode=False,
        )
        response = await provider.chat(request)
        content = getattr(getattr(response, "message", None), "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception as exc:
        logger.warning("Recommendation explanation failed, using template: %s", exc)
    return None
