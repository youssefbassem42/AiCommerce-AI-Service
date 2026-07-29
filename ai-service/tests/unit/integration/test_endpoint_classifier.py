import pytest

from app.application.integration.discovery.endpoint_classifier import EndpointClassifier
from app.application.integration.openapi.parser import EndpointSchema


@pytest.fixture
def classifier() -> EndpointClassifier:
    return EndpointClassifier()


class TestEndpointClassifier:
    def test_classify_list_products(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/products", method="GET")
        result = classifier.classify(ep)
        assert result is not None
        assert result.entity_type == "product"
        assert result.operation == "list"

    def test_classify_detail_product(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/products/{id}", method="GET")
        result = classifier.classify(ep)
        assert result is not None
        assert result.entity_type == "product"
        assert result.operation == "detail"

    def test_classify_create_product(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/products", method="POST")
        result = classifier.classify(ep)
        assert result is not None
        assert result.entity_type == "product"
        assert result.operation == "create"

    def test_classify_delete_order(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/orders/{id}", method="DELETE")
        result = classifier.classify(ep)
        assert result is not None
        assert result.entity_type == "order"
        assert result.operation == "delete"

    def test_classify_customers(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/customers", method="GET")
        result = classifier.classify(ep)
        assert result is not None
        assert result.entity_type == "customer"
        assert result.operation == "list"

    def test_classify_categories(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/categories", method="GET")
        result = classifier.classify(ep)
        assert result is not None
        assert result.entity_type == "category"

    def test_classify_synonym_items_as_product(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/items", method="GET")
        result = classifier.classify(ep)
        assert result is not None
        assert result.entity_type == "product"

    def test_classify_versioned_path(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/v2/products", method="GET")
        result = classifier.classify(ep)
        assert result is not None
        assert result.entity_type == "product"

    def test_classify_update_with_schema(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/products/{id}", method="PUT")
        result = classifier.classify(ep)
        assert result is not None
        assert result.entity_type == "product"
        assert result.operation == "update"

    def test_classify_unknown_entity(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/webhooks", method="GET")
        result = classifier.classify(ep)
        assert result is None

    def test_classify_all(self, classifier: EndpointClassifier) -> None:
        endpoints = [
            EndpointSchema(path="/products", method="GET"),
            EndpointSchema(path="/orders/{id}", method="GET"),
            EndpointSchema(path="/webhooks", method="POST"),
        ]
        results = classifier.classify_all(endpoints)
        assert len(results) == 2

    def test_classify_with_schema_fields(self, classifier: EndpointClassifier) -> None:
        ep = EndpointSchema(path="/products", method="GET")
        fields = {"name", "price", "sku", "description"}
        result = classifier.classify_with_schema(ep, fields)
        assert result is not None
        assert result.entity_type == "product"