"""Phase 10 — AI evaluation suite shared fixtures.

Runs against a REAL LLM provider (default: OpenRouter) so scenario assertions
exercise the actual agentic stack. All external infrastructure (MongoDB,
Qdrant, Redis) is mocked for determinism; the LLM is the only real dependency.

The whole suite is skipped when no provider credentials are configured, so
``pytest tests/eval`` is safe in CI without keys. Run it explicitly:

    EVAL_PROVIDER=openrouter pytest tests/eval -v

Set EVAL_PROVIDER to openai/gemini/claude/mock as needed.
"""

import os

os.environ.setdefault("REQUEST_TIMEOUT", "120")

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ai_exceptions import ProviderCredentialsError
from app.domain.commerce.aggregates.product import Product, Variant
from app.domain.commerce.value_objects.money import Money
from app.infrastructure.providers.factory import LLMProviderFactory

pytestmark = [pytest.mark.eval, pytest.mark.slow]


@pytest.fixture(scope="session")
def llm():
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    provider = os.environ.get("EVAL_PROVIDER", "openrouter")
    try:
        return LLMProviderFactory().get_provider(provider)
    except ProviderCredentialsError as exc:
        pytest.skip(f"Eval suite skipped: {exc}")


def _product(
    pid: str,
    title: str,
    price: str,
    product_type: str,
    tags: list[str],
    stock: int = 10,
) -> Product:
    now = datetime.now(UTC)
    return Product(
        id=pid,
        store_id="store-eval",
        organization_id="org-eval",
        title=title,
        description=title,
        price=Money(amount=Decimal(price), currency="USD"),
        sku=f"SKU-{pid}",
        vendor="EvalStore",
        product_type=product_type,
        tags=tags,
        images=[],
        status="active",
        variants=[
            Variant(
                id=f"v-{pid}",
                sku=f"SKU-{pid}",
                price=Money(amount=Decimal(price), currency="USD"),
                inventory_quantity=stock,
                title="Default",
            )
        ],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture(scope="session")
def catalog() -> list[Product]:
    """Deterministic eval catalog (all priced in USD)."""
    return [
        _product("p-dress-60", "Floral Summer Dress", "60.00", "dress", ["dress", "summer", "floral"]),
        _product("p-dress-120", "Evening Maxi Dress", "120.00", "dress", ["dress", "evening", "maxi"]),
        _product("p-laptop-750", 'Laptop Standard 14"', "750.00", "laptop", ["laptop", "14-inch", "work"]),
        _product("p-laptop-900", 'Laptop Pro 16"', "900.00", "laptop", ["laptop", "16-inch", "gaming", "programming"]),
        _product("p-mouse", "Wireless Mouse", "25.00", "mouse", ["mouse", "wireless"]),
        _product("p-keyboard", "Mechanical Keyboard", "70.00", "keyboard", ["keyboard", "mechanical", "rgb"]),
        _product("p-cable", "USB-C Cable", "15.00", "accessory", ["cable", "usb-c"]),
    ]


@pytest.fixture
def product_repo(catalog):
    """Catalog repo mirroring the real ProductRepository contracts.

    find_many(filters, limit, skip), search(store_id, query, limit) and
    find_by_store(store_id, limit, skip) all refuse any non store-eval scope.
    """
    repo = MagicMock()

    def _terms(text: str) -> set[str]:
        return {t for t in text.lower().replace(",", " ").split() if len(t) > 2}

    def _regex_match(pattern: str, text: str) -> bool:
        import re

        try:
            return re.search(pattern, text, re.IGNORECASE) is not None
        except re.error:
            return pattern.lower() in text.lower()

    def _filters_match(product: Product, filters: dict) -> bool:
        for field, value in filters.items():
            if field in ("store_id", "organization_id"):
                continue
            haystack = getattr(product, field, "") or ""
            if isinstance(haystack, list):
                haystack = " ".join(haystack)
            if isinstance(value, dict) and "$regex" in value:
                if not _regex_match(value["$regex"], str(haystack)):
                    return False
            elif isinstance(value, (list, tuple, set)):
                if not _terms(str(haystack)) & {str(v).lower() for v in value}:
                    return False
            elif str(value).lower() not in str(haystack).lower():
                return False
        return True

    async def find_many(filters=None, limit=100, skip=0, **kwargs):
        filters = filters or {}
        assert filters.get("store_id") == "store-eval", f"cross-tenant catalog access: {filters.get('store_id')}"
        if not filters:
            return catalog[:limit]
        return [p for p in catalog if _filters_match(p, filters)][skip : skip + limit]

    async def search(store_id: str, query: str, limit=20, **kwargs):
        assert store_id == "store-eval", f"cross-tenant catalog search: {store_id}"
        q = _terms(query)
        if not q:
            return catalog[:limit]
        scored = [(p, len(_terms(f"{p.title} {p.product_type} {' '.join(p.tags)}") & q)) for p in catalog]
        return [p for p, score in scored if score > 0][:limit]

    async def find_by_store(store_id: str, limit=20, skip=0, **kwargs):
        assert store_id == "store-eval", f"cross-tenant store scan: {store_id}"
        return catalog[skip : skip + limit]

    async def find_by_id(product_id: str, **kwargs):
        return next((p for p in catalog if p.id == product_id), None)

    async def find_by_external_id(store_id: str, external_id: str, **kwargs):
        return next((p for p in catalog if p.id == external_id), None)

    repo.find_many = AsyncMock(side_effect=find_many)
    repo.search = AsyncMock(side_effect=search)
    repo.find_by_store = AsyncMock(side_effect=find_by_store)
    repo.find_by_id = AsyncMock(side_effect=find_by_id)
    repo.find_by_external_id = AsyncMock(side_effect=find_by_external_id)
    return repo


POLICY_FACTS = {
    "return": ("Return policy", "Items can be returned within 30 days of delivery for a full refund."),
    "shipping": ("Shipping policy", "Standard shipping takes 3-5 business days. Free shipping over $75."),
    "warranty": ("Warranty", "All electronics carry a 12-month manufacturer warranty covering defects."),
    "product": ("Product info", "The store sells dresses, laptops, mice, keyboards, and accessories."),
}


def _chunk(payload: dict, content: str, title: str, score: float = 0.95) -> MagicMock:
    """Vector-search chunk mock with both interfaces the agents use:

    - support/recommendation read ``chunk.metadata``, ``chunk.score``, ``chunk.chunk_id``
    - support facts also call ``chunk.model_dump()``
    """
    mock = MagicMock()
    mock.metadata = payload
    mock.score = score
    mock.chunk_id = payload.get("product_id") or title
    mock.model_dump.return_value = {"content": content, "document_title": title, "metadata": payload}
    return mock


def _product_chunks(catalog: list[Product]) -> list[MagicMock]:
    from app.shared.vector_payloads import EntityType

    chunks = []
    for product in catalog:
        payload = {
            "entity_type": EntityType.PRODUCT.value,
            "product_id": product.id,
            "product_title": product.title,
            "content": product.description,
            "price": float(product.price.amount),
            "currency": product.price.currency,
            "specs": [
                {"name": "category", "value": product.product_type},
                *({"name": "tag", "value": t} for t in product.tags),
            ],
            "store_id": product.store_id,
        }
        chunks.append(_chunk(payload, product.description, product.title))
    return chunks


@pytest.fixture
def retriever_service(catalog):
    """Deterministic vector retriever: policy facts for support queries,
    catalog product payloads for product queries. Routing mirrors production
    RetrievalFilters (entity_type=product vs entity_types=knowledge/policy/faq),
    and every path refuses a non store-eval scope.
    """
    svc = MagicMock()

    async def search(query: str, filters=None, config=None, **kwargs):
        assert filters is None or filters.store_id == "store-eval", "cross-tenant retrieval"
        q = query.lower()
        if filters is not None and getattr(filters, "entity_type", None) == "product":
            matched = [
                c
                for c in _product_chunks(catalog)
                if any(t in q for t in str(c.metadata["product_title"]).lower().split())
            ]
            return MagicMock(results=matched or _product_chunks(catalog)[:2], total=len(matched))
        for key, (title, content) in POLICY_FACTS.items():
            if key in q:
                return MagicMock(results=[_chunk({"entity_type": "policy", "store_id": "store-eval"}, content, title)])
        return MagicMock(results=[], total=0)

    svc.search = AsyncMock(side_effect=search)
    return svc


@pytest.fixture
def ticket_service():
    """Records created tickets so escalation scenarios can assert on them."""
    service = MagicMock()
    service.created = []

    async def create_ticket(**kwargs):
        ticket = MagicMock(ticket_id=f"tk-{len(service.created) + 1}")
        service.created.append((kwargs, ticket))
        return ticket

    async def update_status(**kwargs):
        return MagicMock()

    service.create_ticket = AsyncMock(side_effect=create_ticket)
    service.update_status = AsyncMock(side_effect=update_status)
    return service


@pytest.fixture
def notification_service():
    service = MagicMock()
    service.notify_human = AsyncMock(return_value=None)
    service.notify_customer = AsyncMock(return_value=None)
    return service


@pytest.fixture
def customer_repo():
    repo = MagicMock()
    repo.find_by_id = AsyncMock(return_value=MagicMock(customer_id="cust-eval", email="buyer@eval.test"))
    repo.find_by_email = AsyncMock(return_value=MagicMock(customer_id="cust-eval", email="buyer@eval.test"))
    return repo


@pytest.fixture
def order_repo():
    repo = MagicMock()
    repo.find_by_customer = AsyncMock(return_value=[])
    repo.find_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def escalation_agent(llm, ticket_service, notification_service, customer_repo):
    from app.agents.escalation.agent import EscalationAgent

    return EscalationAgent(
        llm=llm,
        ticket_service=ticket_service,
        notification_service=notification_service,
        customer_repo=customer_repo,
    )


class _MemoryEntry:
    """UserMemory-shaped object the memory nodes read (.id/.key/.value)."""

    def __init__(self, user_id: str, store_id: str, key: str, value: dict):
        self.id = f"mem-{store_id}-{key}"
        self.user_id = user_id
        self.store_id = store_id
        self.key = key
        self.value = value
        self.expires_at = None


class InMemoryMemoryRepository:
    """Dict-backed MemoryRepository mirroring the real positional interface."""

    def __init__(self):
        self._store: dict[tuple[str, str], _MemoryEntry] = {}

    async def find_active_by_key(self, user_id: str, store_id: str, key: str):
        return self._store.get((str(store_id), key))

    async def list_active(self, user_id: str, store_id: str, limit: int = 50):
        entries = [v for (sid, _k), v in self._store.items() if sid == str(store_id)]
        return entries[:limit]

    async def upsert(self, user_id: str, store_id: str, key: str, value: dict, ttl_seconds: int | None = None):
        entry = _MemoryEntry(user_id, store_id, key, value)
        self._store[(str(store_id), key)] = entry
        return entry

    async def delete_by_key(self, user_id: str, store_id: str, key: str) -> bool:
        return self._store.pop((str(store_id), key), None) is not None

    async def delete_expired(self) -> int:
        return 0


@pytest.fixture
def memory_repo():
    return InMemoryMemoryRepository()


def assert_latency(resp) -> None:
    assert resp.latency_ms > 0, "latency must be tracked"
