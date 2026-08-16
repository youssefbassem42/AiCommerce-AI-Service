import json
import logging
from typing import Any

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.core.ai_settings import ai_settings
from app.infrastructure.prompts.client import get_prompt_client
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

SUPPORT_CATEGORIES = {"order_status", "returns", "refund", "technical", "account", "general"}

SUPPORT_TOPICS = {
    "return_policy",
    "shipping",
    "payment",
    "warranty",
    "product",
    "order_status",
    "refund",
    "technical",
    "account",
    "general",
}

SUPPORT_ENTITY_TYPES = ("knowledge", "policy", "faq")

# Query expansion so a long conversation ("what about that?") still retrieves
# the right policy even when the latest message alone has no topic keyword.
TOPIC_QUERY_TERMS = {
    "return_policy": "return policy exchange return window eligibility",
    "shipping": "shipping policy delivery time shipping cost tracking",
    "payment": "payment policy payment methods billing invoice",
    "warranty": "warranty policy coverage repair defect",
    "product": "product specifications features details",
    "order_status": "order status delivery tracking fulfillment",
    "refund": "refund policy money back reimbursement",
    "technical": "technical support login error troubleshooting",
    "account": "account access profile account details",
}

REFUNDABLE_FINANCIAL_STATUSES = {"paid", "partially_paid"}

REFUND_WINDOW_DAYS = 30

# Escalate when the refund exceeds this amount.
REFUND_ESCALATION_THRESHOLD = 500.0


async def categorize_issue(
    query: str,
    history: str = "",
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    """Classify the customer message into a support category."""
    default = {"category": "general", "confidence": 0.0, "order_relevant": False}
    if not llm:
        return default
    try:
        prompt = await get_prompt_client().get("support.categorize_prompt")
        request = ChatRequest(
            messages=[
                MessageDTO(
                    role="system",
                    content="You categorize support messages. Return only valid JSON.",
                ),
                MessageDTO(
                    role="user",
                    content=prompt.format(query=query, history=history[:1500]),
                ),
            ],
            model=ai_settings.DEFAULT_MODEL,
            json_mode=True,
        )
        response = await llm.structured_output(request, dict[str, Any])
        data = json.loads(response.message.content)
        if isinstance(data, dict) and data.get("category") in SUPPORT_CATEGORIES:
            return {
                "category": data["category"],
                "confidence": float(data.get("confidence", 0.0)),
                "order_relevant": bool(data.get("order_relevant", False)),
            }
    except Exception as exc:
        logger.error("Categorization failed: %s", exc, exc_info=True)
    return default


def format_order_for_tracking(order) -> dict[str, Any]:
    """Build a customer-safe summary of an order for tracking purposes."""
    total = order.total_price
    return {
        "id": order.id,
        "external_id": order.external_id,
        "financial_status": order.financial_status,
        "fulfillment_status": order.fulfillment_status,
        "currency": order.currency,
        "total": float(total.amount) if total else 0.0,
        "line_items": [{"title": li.title, "quantity": li.quantity} for li in (order.line_items or [])],
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def evaluate_refund_policy(order) -> dict[str, Any]:
    """Validate refund eligibility and calculate the refundable amount."""
    total = order.total_price
    total_amount = float(total.amount) if total else 0.0
    cancelled = order.cancelled_at is not None
    eligible = not cancelled and order.financial_status in REFUNDABLE_FINANCIAL_STATUSES and total_amount > 0
    return {
        "eligible": eligible,
        "amount": total_amount if eligible else None,
        "cancelled": cancelled,
        "financial_status": order.financial_status,
    }


async def detect_topic(
    query: str,
    history: str = "",
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    """Detect the fine-grained support topic for targeted knowledge retrieval."""
    default = {"topic": "general", "product_mention": None}
    if not llm:
        return default
    try:
        prompt = await get_prompt_client().get("support.topic_detect_prompt")
        request = ChatRequest(
            messages=[
                MessageDTO(
                    role="system",
                    content="You detect support topics. Return only valid JSON.",
                ),
                MessageDTO(
                    role="user",
                    content=prompt.format(query=query, history=history[:1500]),
                ),
            ],
            model=ai_settings.DEFAULT_MODEL,
            json_mode=True,
        )
        response = await llm.structured_output(request, dict[str, Any])
        data = json.loads(response.message.content)
        topic = data.get("topic") if isinstance(data, dict) else None
        if topic in SUPPORT_TOPICS:
            return {
                "topic": topic,
                "product_mention": data.get("product_mention") or None,
            }
    except Exception as exc:
        logger.error("Topic detection failed: %s", exc, exc_info=True)
    return default


def _retrieval_query(query: str, topic: str) -> str:
    """Augment the raw query with topic terms so long conversations stay on-topic."""
    terms = TOPIC_QUERY_TERMS.get(topic)
    if not terms or terms in query.lower():
        return query
    return f"{query} {terms}"


def _facts_from_chunks(chunks: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    """Normalize raw retrieved chunks into a fact list safe to feed the LLM."""
    facts: list[dict[str, Any]] = []
    for chunk in chunks[:limit]:
        title = chunk.get("document_title") or (chunk.get("metadata") or {}).get("document_title", "")
        content = (chunk.get("content") or "")[:2000]
        if not content:
            continue
        facts.append({"source": title, "content": content})
    return facts


def facts_from_context(context: dict[str, Any] | None, limit: int = 6) -> list[dict[str, Any]]:
    """Extract verified policy/knowledge facts already retrieved by the Context Builder."""
    if not context:
        return []
    chunks = list(context.get("knowledge_context") or [])
    facts = _facts_from_chunks(chunks, limit=limit)

    business_rules = context.get("business_rules") or {}
    summary = business_rules.get("business_summary")
    if summary and len(facts) < limit:
        facts.append({"source": "Store business summary", "content": str(summary)[:2000]})
    return facts


async def retrieve_support_facts(
    query: str,
    topic: str,
    store_id: str,
    retriever_service: Any | None = None,
    context: dict[str, Any] | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Retrieve intent-specific verified facts (policy/FAQ/knowledge) for the topic.

    Falls back to the context-builder chunks when no retriever is available.
    """
    if retriever_service:
        try:
            tenant = (context or {}).get("tenant") or {}
            filters = RetrievalFilters(
                organization_id=tenant.get("organization_id"),
                store_id=store_id,
                entity_types=list(SUPPORT_ENTITY_TYPES),
            )
            config = RetrievalConfig(
                top_k=limit,
                score_threshold=0.2,
                use_hybrid=True,
                use_mmr=True,
            )
            result = await retriever_service.search(
                query=_retrieval_query(query, topic),
                filters=filters,
                config=config,
            )
            facts = _facts_from_chunks([c.model_dump() for c in result.results], limit=limit)
            if facts:
                return facts
        except Exception as exc:
            logger.warning("Support fact retrieval failed: %s", exc, exc_info=True)

    return facts_from_context(context, limit=limit)


def format_facts_for_prompt(facts: list[dict[str, Any]]) -> str:
    """Render verified facts for the reply prompt.

    Facts are untrusted retrieved data: instruction-like directives inside
    document content are redacted before the text reaches the LLM (Phase 9
    knowledge-poisoning guardrail).
    """
    from app.utils.content_guard import guard_facts

    guarded = guard_facts(facts)
    if not guarded:
        return "(no store facts available)"
    parts = []
    for i, fact in enumerate(guarded, start=1):
        parts.append(f"[{i}] {fact.get('source', 'Store knowledge')}\n{fact.get('content', '')}")
    return "\n\n".join(parts)


def format_memory_for_prompt(memory: dict[str, Any] | None) -> str:
    """Render recalled customer/session memory for the reply prompt."""
    if not memory:
        return "(none)"
    entries = memory.get("entries") or memory
    if not isinstance(entries, dict) or not entries:
        return "(none)"
    lines = [f"{key}: {value}" for key, value in entries.items() if key != "last_exchange"]
    exchange = entries.get("last_exchange")
    if isinstance(exchange, dict):
        lines.append(
            f"previous exchange: user asked '{exchange.get('user', '')}', we said '{exchange.get('assistant', '')}'"
        )
    return "\n".join(lines) if lines else "(none)"


def format_order_for_prompt(order) -> str:
    """Render the order facts for the reply prompt (customer-safe)."""
    if not order:
        return "(no order found)"
    info = format_order_for_tracking(order)
    lines = [
        f"Order {info['external_id'] or info['id']}",
        f"Fulfillment status: {info['fulfillment_status'] or 'in progress'}",
        f"Financial status: {info['financial_status']}",
    ]
    items = ", ".join(f"{li['quantity']}x {li['title']}" for li in info["line_items"])
    if items:
        lines.append(f"Items: {items}")
    if info["created_at"]:
        lines.append(f"Placed: {info['created_at']}")
    return "\n".join(lines)


def product_to_card(product: Any) -> dict[str, Any] | None:
    """Build a customer-safe product card from a domain Product aggregate."""
    if product is None:
        return None
    price = getattr(product, "price", None)
    amount = float(price.amount) if price is not None else None
    currency = price.currency if price is not None else "USD"
    variants = []
    for variant in getattr(product, "variants", None) or []:
        variants.append(
            {
                "sku": variant.sku,
                "title": variant.title,
                "price": float(variant.price.amount) if variant.price is not None else None,
                "currency": variant.price.currency if variant.price is not None else currency,
                "inventory_quantity": variant.inventory_quantity,
            }
        )
    images = list(getattr(product, "images", None) or [])
    image_url = images[0].url if images else None
    return {
        "product_id": product.id,
        "title": product.title,
        "description": product.description,
        "price": amount,
        "currency": currency,
        "vendor": product.vendor,
        "product_type": product.product_type,
        "tags": list(product.tags or []),
        "variants": variants,
        "inventory_quantity": getattr(product, "inventory_quantity", 0),
        "image_url": image_url,
    }


async def search_product_cards(
    product_repo: Any | None,
    store_id: str,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Look up actual store products matching the customer's mention."""
    if not product_repo:
        return []
    try:
        products = await product_repo.search(store_id, query, limit=limit)
    except Exception as exc:
        logger.warning("Product search failed, falling back to store scan: %s", exc)
        products = []
    if not products:
        try:
            products = await product_repo.find_by_store(store_id, limit=100)
            lowered = query.lower()
            products = [
                p for p in products if lowered in (p.title or "").lower() or lowered in " ".join(p.tags or []).lower()
            ][:limit]
        except Exception as exc:
            logger.warning("Product scan failed: %s", exc, exc_info=True)
            return []
    return [card for p in products if (card := product_to_card(p))]
