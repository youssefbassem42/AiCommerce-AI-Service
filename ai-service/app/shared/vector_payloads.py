"""Canonical vector payload model shared by every indexer and consumer.

Every point upserted into a tenant vector collection MUST carry at least the
canonical identity fields below, and exactly one ``entity_type``. Consumers
(recommendation, RAG) filter on ``entity_type`` so that product retrieval can
never resolve to knowledge chunks, FAQs, policies or reviews.

Canonical common fields::

    store_id
    organization_id
    entity_id
    entity_type
    source_type
    document_status

Products additionally carry::

    product_id
    product_title
    price
    currency
    category_id
    brand_id
    specs

Knowledge chunks additionally carry::

    document_id
    chunk_id
    document_type
    knowledge_scope
"""

from enum import StrEnum
from typing import Any

ENTITY_TYPE_KEY = "entity_type"
ENTITY_ID_KEY = "entity_id"
STORE_ID_KEY = "store_id"
ORGANIZATION_ID_KEY = "organization_id"
SOURCE_TYPE_KEY = "source_type"
DOCUMENT_STATUS_KEY = "document_status"


class EntityType(StrEnum):
    """Canonical entity types that may exist in a vector collection."""

    PRODUCT = "product"
    KNOWLEDGE = "knowledge"
    CATEGORY = "category"
    POLICY = "policy"
    FAQ = "faq"
    REVIEW = "review"
    ORDER = "order"

    @classmethod
    def as_value(cls, value: Any) -> str:
        if isinstance(value, EntityType):
            return value.value
        return str(value)


def base_entity_payload(
    *,
    organization_id: str | None,
    store_id: str | None,
    entity_type: str | EntityType,
    entity_id: str,
    source_type: str,
    document_status: str = "active",
    **extra: Any,
) -> dict[str, Any]:
    """Build the canonical common payload fields shared by all entity types."""
    payload: dict[str, Any] = {
        STORE_ID_KEY: store_id,
        ORGANIZATION_ID_KEY: organization_id,
        ENTITY_TYPE_KEY: EntityType.as_value(entity_type),
        ENTITY_ID_KEY: entity_id,
        SOURCE_TYPE_KEY: source_type,
        DOCUMENT_STATUS_KEY: document_status,
    }
    payload.update(extra)
    return payload


def product_payload(
    *,
    organization_id: str | None,
    store_id: str | None,
    product_id: str,
    title: str,
    content: str,
    source_type: str = "integration_sync",
    price: float | None = None,
    currency: str | None = None,
    category_id: str | None = None,
    brand_id: str | None = None,
    specs: list[dict[str, Any]] | None = None,
    document_status: str = "active",
    **extra: Any,
) -> dict[str, Any]:
    """Build a canonical product payload."""
    payload = base_entity_payload(
        organization_id=organization_id,
        store_id=store_id,
        entity_type=EntityType.PRODUCT,
        entity_id=product_id,
        source_type=source_type,
        document_status=document_status,
        product_id=product_id,
        product_title=title,
        content=content,
    )
    if price is not None:
        payload["price"] = price
    if currency:
        payload["currency"] = currency
    if category_id:
        payload["category_id"] = category_id
    if brand_id:
        payload["brand_id"] = brand_id
    if specs:
        payload["specs"] = specs
    payload.update(extra)
    return payload


def knowledge_payload(
    *,
    organization_id: str | None,
    store_id: str | None,
    chunk_id: str,
    document_id: str,
    document_type: str | None = None,
    knowledge_scope: str | None = None,
    content: str = "",
    source_type: str = "knowledge_document",
    document_status: str = "active",
    **extra: Any,
) -> dict[str, Any]:
    """Build a canonical knowledge chunk payload."""
    payload = base_entity_payload(
        organization_id=organization_id,
        store_id=store_id,
        entity_type=EntityType.KNOWLEDGE,
        entity_id=document_id,
        source_type=source_type,
        document_status=document_status,
        document_id=document_id,
        chunk_id=chunk_id,
        content=content,
    )
    if document_type:
        payload["document_type"] = document_type
    if knowledge_scope:
        payload["knowledge_scope"] = knowledge_scope
    payload.update(extra)
    return payload
