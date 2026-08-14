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

import pytest
from unittest.mock import AsyncMock, MagicMock

from decimal import Decimal
from datetime import UTC, datetime

from app.core.ai_exceptions import ProviderCredentialsError
from app.domain.commerce.aggregates.product import Product, Variant
from app.domain.commerce.value_objects.money import Money
from app.infrastructure.providers.factory import LLMProviderFactory

pytestmark = [pytest.mark.eval, pytest.mark.slow]


@pytest.fixture(scope="session")
def llm():
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
        _product("p-laptop-750", "Laptop Standard 14\"", "750.00", "laptop", ["laptop", "14-inch", "work"]),
        _product("p-laptop-900", "Laptop Pro 16\"", "900.00", "laptop", ["laptop", "16-inch", "gaming", "programming"]),
        _product("p-mouse", "Wireless Mouse", "25.00", "mouse", ["mouse", "wireless"]),
        _product("p-keyboard", "Mechanical Keyboard", "70.00", "keyboard", ["keyboard", "mechanical", "rgb"]),
        _product("p-cable", "USB-C Cable", "15.00", "accessory", ["cable", "usb-c"]),
    ]


@pytest.fixture
def product_repo(catalog):
    """Keyword-based catalog search; always scoped to store-eval."""
    repo = MagicMock()

    def _matches(product: Product, query: str) -> bool:
        q = query.lower()
        haystack = " ".join(
            [product.title, product.product_type, " ".join(product.tags)]
        ).lower()
        return any(term in haystack for term in q.replace(",", " ").split() if len(term) > 2)

    async def find_many(*, store_id: str, query: str | None = None, **kwargs) -> list[Product]:
        assert store_id == "store-eval", f"cross-tenant catalog access: {store_id}"
        if not query:
            return catalog
        return [p for p in catalog if _matches(p, query)] or catalog

    async def find_by_id(product_id: str, **kwargs):
        return next((p for p in catalog if p.id == product_id), None)

    repo.find_many = AsyncMock(side_effect=find_many)
    repo.find_by_id = AsyncMock(side_effect=find_by_id)
    return repo


POLICY_FACTS = {
    "return": ("Return policy", "Items can be returned within 30 days of delivery for a full refund."),
    "shipping": ("Shipping policy", "Standard shipping takes 3-5 business days. Free shipping over $75."),
    "warranty": ("Warranty", "All electronics carry a 12-month manufacturer warranty covering defects."),
    "product": ("Product info", "The store sells dresses, laptops, mice, keyboards, and accessories."),
}


@pytest.fixture
def retriever_service():
    """Policy FAQ retriever; facts are store-eval scoped by construction."""
    svc = MagicMock()

    async def search(query: str, filters=None, config=None, **kwargs):
        assert filters is None or filters.store_id == "store-eval", "cross-tenant retrieval"
        q = query.lower()
        for key, (title, content) in POLICY_FACTS.items():
            if key in q:
                return [
                    MagicMock(
                        model_dump=lambda: {
                            "content": content,
                            "document_title": title,
                            "metadata": {"store_id": "store-eval"},
                        }
                    )
                ]
        return []

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


class InMemoryMemoryRepository:
    """Dict-backed MemoryRepository for deterministic multi-turn eval."""

    def __init__(self):
        self._store: dict[tuple[str, str], dict] = {}

    async def find_active_by_key(self, *, user_id: str | None, store_id: str | None, key: str, **kwargs):
        return self._store.get((str(store_id), key))

    async def list_active(self, *, user_id: str | None, store_id: str | None, **kwargs):
        return [v for (sid, _k), v in self._store.items() if sid == str(store_id)]

    async def upsert(self, *, user_id: str | None, store_id: str | None, key: str, value: dict, **kwargs):
        self._store[(str(store_id), key)] = value
        return value

    async def delete_by_key(self, *, user_id: str | None, store_id: str | None, key: str, **kwargs):
        self._store.pop((str(store_id), key), None)
        return True

    async def delete_expired(self, **kwargs):
        return 0


@pytest.fixture
def memory_repo():
    return InMemoryMemoryRepository()


def assert_latency(resp) -> None:
    assert resp.latency_ms > 0, "latency must be tracked"