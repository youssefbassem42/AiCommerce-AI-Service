import json
from unittest.mock import MagicMock

import pytest

from app.application.integration.mapping.canonical_schema import (
    CANONICAL_SCHEMAS,
    canonical_schema_for,
    canonical_targets,
)
from app.application.integration.mapping.llm_mapper import LlmEntityMapper
from app.application.integration.sync.orchestrator import SyncOrchestrator
from app.domain.integration.entities.integration_connection import ConnectionStatus, IntegrationConnection
from app.domain.integration.value_objects.auth_config import AuthConfig
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig, PaginationStyle


def make_entity_mapping(entity_type: str = "product", fields: list[FieldMapping] | None = None) -> EntityMapping:
    return EntityMapping(
        entity_type=entity_type,
        list_path=f"/api/{entity_type}s",
        list_method="GET",
        id_field="id",
        pagination=PaginationConfig(style=PaginationStyle.NONE),
        field_mappings=fields or [FieldMapping(source="title", target="title")],
    )


def fake_chat_response(content: str) -> MagicMock:
    response = MagicMock()
    response.message.content = content
    return response


class FakeProvider:
    def __init__(self, result_content: str | None = None, error: Exception | None = None):
        self._result = result_content
        self._error = error
        self.calls = 0

    async def structured_output(self, request, response_schema, timeout=None):  # noqa: ARG002
        self.calls += 1
        if self._error:
            raise self._error
        return fake_chat_response(self._result)


class FakeFactory:
    def __init__(self, provider: FakeProvider):
        self._provider = provider

    def get_provider(self, name):  # noqa: ARG002
        return self._provider


def make_connection(entity_type: str = "product") -> IntegrationConnection:
    return IntegrationConnection(
        id="conn1",
        store_id="s1",
        organization_id="o1",
        name="Test Connection",
        platform_name="test",
        status=ConnectionStatus.ACTIVE,
        auth_config=AuthConfig(type="apiKey", name="X-API-Key"),
        entity_mappings=[make_entity_mapping(entity_type)],
    )


class TestCanonicalSchema:
    def test_product_schema_required_title(self):
        schema = canonical_schema_for("product")
        assert schema is not None
        title = next(f for f in schema["fields"] if f["name"] == "title")
        assert title["required"] is True

    def test_unknown_entity_returns_none(self):
        assert canonical_schema_for("blob") is None
        assert canonical_targets("blob") == set()

    def test_all_entity_types_registered(self):
        for entity in ("product", "order", "customer", "category", "inventory"):
            assert entity in CANONICAL_SCHEMAS


class TestLlmEntityMapper:
    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        mapper = LlmEntityMapper(enabled=False, provider_factory=FakeFactory(FakeProvider("{}")))
        result = await mapper.build_entity_mapping("product", make_entity_mapping("product"), {}, [{"title": "X"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_provider_failure_falls_back_to_none(self):
        provider = FakeProvider(error=RuntimeError("provider down"))
        mapper = LlmEntityMapper(provider_factory=FakeFactory(provider))
        result = await mapper.build_entity_mapping("product", make_entity_mapping("product"), {}, [{"title": "X"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_mapping_sanitized_against_canonical(self):
        content = json.dumps(
            {
                "entity_type": "product",
                "field_mappings": [
                    {"source": "name", "target": "title", "required": True},
                    {"source": "pricing.amount", "target": "price", "transformer": "money_to_amount"},
                    {"source": "bogus", "target": "not_a_canonical_field"},
                    {"source": "id", "target": "external_id"},
                ],
            }
        )
        provider = FakeProvider(content)
        mapper = LlmEntityMapper(provider_factory=FakeFactory(provider))
        current = make_entity_mapping()
        result = await mapper.build_entity_mapping("product", current, {}, [{"name": "Widget"}])

        assert result is not None
        targets = {fm.target for fm in result.field_mappings}
        assert {"title", "price", "external_id"} <= targets
        assert "not_a_canonical_field" not in targets
        assert result.list_path == current.list_path

    @pytest.mark.asyncio
    async def test_json_content_parse(self):
        provider = FakeProvider(
            json.dumps({"entity_type": "product", "field_mappings": [{"source": "sku", "target": "sku"}]})
        )
        mapper = LlmEntityMapper(provider_factory=FakeFactory(provider))
        result = await mapper.build_entity_mapping("product", make_entity_mapping(), {}, [{"sku": "A1"}])
        assert result is not None
        sku = next(fm for fm in result.field_mappings if fm.target == "sku")
        assert sku.source == "sku"

    def test_fingerprint_stable(self):
        mapper = LlmEntityMapper(enabled=False)
        fp1 = mapper.fingerprint({"a": 1, "b": "x"})
        fp2 = mapper.fingerprint({"b": "x", "a": 1})
        assert fp1 == fp2
        assert mapper.fingerprint({"a": 1}) != fp1


class TestOrchestratorLlmWiring:
    @pytest.mark.asyncio
    async def test_llm_mapping_applied_and_persisted(self):
        provider = FakeProvider(
            json.dumps({"entity_type": "product", "field_mappings": [{"source": "name", "target": "title"}]})
        )
        mapper = LlmEntityMapper(provider_factory=FakeFactory(provider))
        orch = SyncOrchestrator(llm_mapper=mapper)
        connection = make_connection()
        samples = [{"name": "Widget", "price": "12"}]

        result = await orch._resolve_llm_mapping(connection, connection.entity_mappings[0], samples)

        assert result is not None
        assert provider.calls == 1
        assert connection.entity_mappings[0].field_mappings[0].target == "title"
        assert connection.llm_mapping_sources.get("product")

    @pytest.mark.asyncio
    async def test_persisted_fingerprint_reuses_without_llm_call(self):
        provider = FakeProvider(
            json.dumps({"entity_type": "product", "field_mappings": [{"source": "name", "target": "title"}]})
        )
        mapper = LlmEntityMapper(provider_factory=FakeFactory(provider))
        orch = SyncOrchestrator(llm_mapper=mapper)
        connection = make_connection()
        samples = [{"name": "Widget"}]

        await orch._resolve_llm_mapping(connection, connection.entity_mappings[0], samples)
        assert provider.calls == 1

        connection2 = connection.model_copy(deep=True)
        result = await orch._resolve_llm_mapping(connection2, connection2.entity_mappings[0], samples)
        assert result is not None
        assert provider.calls == 1, "second sync must not call the LLM again"

    @pytest.mark.asyncio
    async def test_mapper_failure_keeps_rule_mapping(self):
        provider = FakeProvider(error=RuntimeError("boom"))
        mapper = LlmEntityMapper(provider_factory=FakeFactory(provider))
        orch = SyncOrchestrator(llm_mapper=mapper)
        connection = make_connection()

        result = await orch._resolve_llm_mapping(connection, connection.entity_mappings[0], [{"title": "X"}])

        assert result is connection.entity_mappings[0]
        assert connection.llm_mapping_sources.get("product") is None
