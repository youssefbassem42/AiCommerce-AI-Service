import logging
import re
from typing import Optional

from app.application.integration.openapi.parser import EndpointSchema

logger = logging.getLogger(__name__)

ENTITY_SYNONYMS: dict[str, str] = {
    "items": "product",
    "goods": "product",
    "merchandise": "product",
    "clients": "customer",
    "users": "customer",
    "accounts": "customer",
    "subscribers": "customer",
    "purchases": "order",
    "invoices": "order",
    "transactions": "order",
    "categories": "category",
    "collections": "category",
    "brands": "product",
    "variants": "product",
    "skus": "product",
    "inventory": "product",
    "stock": "product",
    "shipments": "order",
    "fulfillments": "order",
}

PRODUCT_FIELDS = {"name", "price", "sku", "description", "title", "product_type"}
ORDER_FIELDS = {"total", "subtotal", "currency", "email", "line_items", "financial_status"}
CUSTOMER_FIELDS = {"email", "first_name", "last_name", "phone", "addresses"}


class ClassifiedEndpoint:
    def __init__(
        self,
        entity_type: str,
        operation: str,
        endpoint: EndpointSchema,
        confidence: float = 1.0,
    ):
        self.entity_type = entity_type
        self.operation = operation
        self.endpoint = endpoint
        self.confidence = confidence


class EndpointClassifier:
    """Classify endpoints by entity type and operation using path heuristics + schema inference."""

    def classify(
        self, endpoint: EndpointSchema
    ) -> Optional[ClassifiedEndpoint]:
        clean_path = self._strip_version_prefix(endpoint.path)
        segments = self._path_segments(clean_path)

        entity_type = self._detect_entity_from_path(segments)
        if entity_type:
            operation = self._detect_operation(endpoint, clean_path)
            return ClassifiedEndpoint(
                entity_type=entity_type,
                operation=operation,
                endpoint=endpoint,
                confidence=0.8,
            )

        return None

    def classify_with_schema(
        self,
        endpoint: EndpointSchema,
        field_names: set[str],
    ) -> Optional[ClassifiedEndpoint]:
        path_classification = self.classify(endpoint)
        if path_classification and path_classification.confidence >= 0.7:
            return path_classification

        entity_from_schema = self._detect_entity_from_fields(field_names)
        if entity_from_schema:
            operation = self._detect_operation(endpoint, endpoint.path)
            return ClassifiedEndpoint(
                entity_type=entity_from_schema,
                operation=operation,
                endpoint=endpoint,
                confidence=0.6,
            )

        return path_classification

    def classify_all(
        self,
        endpoints: list[EndpointSchema],
        resolved_field_map: Optional[dict[str, set[str]]] = None,
    ) -> list[ClassifiedEndpoint]:
        result: list[ClassifiedEndpoint] = []
        for ep in endpoints:
            if resolved_field_map and ep.path in resolved_field_map:
                c = self.classify_with_schema(ep, resolved_field_map[ep.path])
            else:
                c = self.classify(ep)
            if c:
                result.append(c)
        return result

    @staticmethod
    def _strip_version_prefix(path: str) -> str:
        return re.sub(r"^/v[0-9]+(/?)", "/", path)

    @staticmethod
    def _path_segments(path: str) -> list[str]:
        return [s for s in path.strip("/").split("/") if s and not s.startswith("{")]

    @staticmethod
    def _detect_entity_from_path(segments: list[str]) -> Optional[str]:
        if not segments:
            return None
        candidate = segments[-1].lower()
        singular = candidate.rstrip("s")
        singular = ENTITY_SYNONYMS.get(candidate, singular)
        if singular in {"product", "order", "customer", "category"}:
            return singular
        return None

    @staticmethod
    def _detect_operation(endpoint: EndpointSchema, clean_path: str) -> str:
        has_id_param = "{" in endpoint.path
        method = endpoint.method

        if method == "GET":
            return "detail" if has_id_param else "list"
        if method == "POST":
            return "create"
        if method == "PUT" or method == "PATCH":
            return "update"
        if method == "DELETE":
            return "delete"
        return "unknown"

    @staticmethod
    def _detect_entity_from_fields(field_names: set[str]) -> Optional[str]:
        name_lower = {f.lower().replace("_", "") for f in field_names}
        product_score = len(PRODUCT_FIELDS & name_lower)
        order_score = len(ORDER_FIELDS & name_lower)
        customer_score = len(CUSTOMER_FIELDS & name_lower)

        scores = [
            ("product", product_score),
            ("order", order_score),
            ("customer", customer_score),
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        best_type, best_score = scores[0]
        if best_score >= 2:
            return best_type
        return None