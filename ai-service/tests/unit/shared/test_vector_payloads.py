from app.shared.vector_payloads import (
    EntityType,
    base_entity_payload,
    knowledge_payload,
    product_payload,
)


class TestEntityType:
    def test_canonical_values(self):
        assert EntityType.PRODUCT.value == "product"
        assert EntityType.KNOWLEDGE.value == "knowledge"
        assert EntityType.CATEGORY.value == "category"
        assert EntityType.POLICY.value == "policy"
        assert EntityType.FAQ.value == "faq"
        assert EntityType.REVIEW.value == "review"

    def test_as_value_accepts_enum_and_string(self):
        assert EntityType.as_value(EntityType.PRODUCT) == "product"
        assert EntityType.as_value("knowledge") == "knowledge"


class TestBaseEntityPayload:
    def test_canonical_common_fields(self):
        payload = base_entity_payload(
            organization_id="o1",
            store_id="s1",
            entity_type=EntityType.PRODUCT,
            entity_id="p1",
            source_type="integration_sync",
        )
        assert payload["store_id"] == "s1"
        assert payload["organization_id"] == "o1"
        assert payload["entity_type"] == "product"
        assert payload["entity_id"] == "p1"
        assert payload["source_type"] == "integration_sync"
        assert payload["document_status"] == "active"

    def test_document_status_override(self):
        payload = base_entity_payload(
            organization_id="o1",
            store_id="s1",
            entity_type="knowledge",
            entity_id="d1",
            source_type="knowledge_document",
            document_status="archived",
        )
        assert payload["document_status"] == "archived"

    def test_extra_fields_merged(self):
        payload = base_entity_payload(
            organization_id="o1",
            store_id="s1",
            entity_type="category",
            entity_id="c1",
            source_type="integration_sync",
            document_title="Electronics",
        )
        assert payload["document_title"] == "Electronics"


class TestProductPayload:
    def test_canonical_product_fields(self):
        payload = product_payload(
            organization_id="o1",
            store_id="s1",
            product_id="p1",
            title="Laptop X",
            content="Laptop X description",
            price=499.99,
            currency="USD",
            category_id="cat-1",
            brand_id="brand-1",
            specs=[{"name": "ram", "value": "16GB"}],
        )
        assert payload["entity_type"] == "product"
        assert payload["entity_id"] == "p1"
        assert payload["product_id"] == "p1"
        assert payload["product_title"] == "Laptop X"
        assert payload["price"] == 499.99
        assert payload["currency"] == "USD"
        assert payload["category_id"] == "cat-1"
        assert payload["brand_id"] == "brand-1"
        assert payload["specs"] == [{"name": "ram", "value": "16GB"}]
        assert payload["document_status"] == "active"

    def test_optional_fields_omitted(self):
        payload = product_payload(
            organization_id="o1",
            store_id="s1",
            product_id="p1",
            title="Laptop X",
            content="desc",
        )
        assert "price" not in payload
        assert "currency" not in payload
        assert "category_id" not in payload
        assert "brand_id" not in payload
        assert "specs" not in payload


class TestKnowledgePayload:
    def test_canonical_knowledge_fields(self):
        payload = knowledge_payload(
            organization_id="o1",
            store_id="s1",
            chunk_id="chunk-1",
            document_id="doc-1",
            document_type="faq",
            knowledge_scope="store",
            content="Some text",
        )
        assert payload["entity_type"] == "knowledge"
        assert payload["entity_id"] == "doc-1"
        assert payload["chunk_id"] == "chunk-1"
        assert payload["document_id"] == "doc-1"
        assert payload["document_type"] == "faq"
        assert payload["knowledge_scope"] == "store"
        assert payload["content"] == "Some text"
        assert payload["source_type"] == "knowledge_document"
        assert payload["document_status"] == "active"

    def test_optional_fields_omitted(self):
        payload = knowledge_payload(
            organization_id="o1",
            store_id="s1",
            chunk_id="c1",
            document_id="d1",
        )
        assert "document_type" not in payload
        assert "knowledge_scope" not in payload
