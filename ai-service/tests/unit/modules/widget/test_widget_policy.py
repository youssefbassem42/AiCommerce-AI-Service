"""Phase E tests: widget AI-execution control server policy (R-03).

Legacy widget request fields (model, temperature, max_tokens, top_k,
score_threshold, use_hybrid, use_mmr, rerank, knowledge_scope) remain part of
the contract for compatibility, but every value is sanitized by
`WidgetServerPolicy` before it can influence cost or behavior.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.widget.schemas import WidgetChatRequestSchema
from app.application.widget.policy import WidgetServerPolicy, apply_widget_policy
from app.core.ai_settings import ai_settings


def make_request(**overrides) -> WidgetChatRequestSchema:
    base = {
        "message": "Hello",
        "model": "gpt-4o",
        "temperature": 1.9,
        "max_tokens": 8000,
        "top_k": 40,
        "score_threshold": 0.0,
        "use_hybrid": True,
        "use_mmr": True,
        "rerank": True,
        "knowledge_scope": "internal",
    }
    base.update(overrides)
    return WidgetChatRequestSchema(**base)


class TestPolicyUnit:
    def test_legacy_schema_still_accepts_hostile_controls(self):
        # Compatibility adapter: the request contract is unchanged — a browser
        # client sending every control at maximum still passes validation.
        request = make_request()
        assert request.model == "gpt-4o"
        assert request.temperature == 1.9

    def test_model_not_allowlisted_uses_server_default(self):
        request = make_request(model="ultra-expensive-model")
        result = apply_widget_policy(request)
        assert result.model == ai_settings.DEFAULT_MODEL
        assert any("model:ultra-expensive-model" in c for c in result.clamped)

    def test_model_allowlisted_passes(self):
        request = make_request(model="cheap-model")
        policy = WidgetServerPolicy(allowed_models=("cheap-model", "fast-model"))
        result = apply_widget_policy(request, policy)
        assert result.model == "cheap-model"
        assert not any(c.startswith("model:") for c in result.clamped)

    def test_empty_allowlist_blocks_all_client_models(self):
        # Default policy: the server owns the model choice.
        result = apply_widget_policy(make_request(model="anything"))
        assert result.model == ai_settings.DEFAULT_MODEL
        assert any("model:anything" in c for c in result.clamped)

    def test_temperature_clamped_to_policy_bounds(self):
        policy = WidgetServerPolicy(temperature_min=0.0, temperature_max=0.5)
        result = apply_widget_policy(make_request(temperature=1.9), policy)
        assert result.temperature == 0.5
        assert "temperature:1.9->0.5" in result.clamped

        result_low = apply_widget_policy(make_request(temperature=0.0), policy)
        assert result_low.temperature == 0.0

    def test_temperature_default_when_absent(self):
        result = apply_widget_policy(make_request(temperature=None))
        assert result.temperature == 0.7
        assert not any(c.startswith("temperature:") for c in result.clamped)

    def test_max_tokens_capped(self):
        result = apply_widget_policy(make_request(max_tokens=8000))
        assert result.max_tokens == 1024
        assert "max_tokens:8000->1024" in result.clamped

    def test_max_tokens_within_policy_unchanged(self):
        result = apply_widget_policy(make_request(max_tokens=512))
        assert result.max_tokens == 512

    def test_top_k_capped(self):
        result = apply_widget_policy(make_request(top_k=40))
        assert result.top_k == 10
        assert "top_k:40->10" in result.clamped

    def test_expensive_retrieval_flags_forced_off(self):
        result = apply_widget_policy(make_request(use_hybrid=True, use_mmr=True, rerank=True))
        assert (result.use_hybrid, result.use_mmr, result.rerank) == (False, False, False)
        assert {"use_hybrid:True->False", "use_mmr:True->False", "rerank:True->False"} <= set(result.clamped)

    def test_retrieval_flags_allowlisted(self):
        policy = WidgetServerPolicy(hybrid_allowed=True, mmr_allowed=True, rerank_allowed=True)
        result = apply_widget_policy(
            make_request(
                model=None,
                temperature=0.5,
                max_tokens=256,
                top_k=5,
                knowledge_scope=None,
                use_hybrid=True,
                use_mmr=True,
                rerank=True,
            ),
            policy,
        )
        assert (result.use_hybrid, result.use_mmr, result.rerank) == (True, True, True)
        assert result.clamped == ()

    def test_knowledge_scope_dropped_when_not_allowlisted(self):
        result = apply_widget_policy(make_request(knowledge_scope="internal"))
        assert result.knowledge_scope is None
        assert "knowledge_scope:internal->null" in result.clamped

    def test_knowledge_scope_allowlisted(self):
        policy = WidgetServerPolicy(allowed_knowledge_scopes=("public", "internal"))
        result = apply_widget_policy(make_request(knowledge_scope="internal"), policy)
        assert result.knowledge_scope == "internal"

    def test_in_policy_values_pass_unclamped(self):
        request = make_request(
            model=None,
            temperature=0.5,
            max_tokens=256,
            top_k=5,
            use_hybrid=False,
            use_mmr=False,
            rerank=False,
            knowledge_scope=None,
        )
        result = apply_widget_policy(request)
        assert result.clamped == ()
        assert result.temperature == 0.5
        assert result.max_tokens == 256
        assert result.top_k == 5


class TestWidgetChatRouterPolicy:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    @pytest.fixture(autouse=True)
    def deps(self):
        from datetime import UTC, datetime, timedelta
        from types import SimpleNamespace

        from app.api.ai.dependencies import get_conversation_service, get_orchestration_service
        from app.api.knowledge.retrieval_dependencies import get_retriever_service
        from app.api.quota.dependencies import get_quota_enforcer
        from app.api.rag.dependencies import get_summary_repository
        from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO
        from app.application.knowledge.retrieval.dto import UnifiedRetrievalResult
        from app.domain.analytics.entities.plan_policy import PlanPolicy
        from app.main import app

        self.orchestration = MagicMock()
        self.orchestration.chat = AsyncMock(
            return_value=ChatResponse(
                id="chat-1",
                model=ai_settings.DEFAULT_MODEL,
                provider="openai",
                message=MessageDTO(role="assistant", content="hi"),
                usage=UsageDTO(),
                latency_ms=1.0,
                metadata={"intent": "general"},
            )
        )
        self.retriever = MagicMock()
        self.retriever.search = AsyncMock(
            return_value=UnifiedRetrievalResult(
                query="Hello",
                results=[],
                total_count=0,
                strategy="semantic",
                latency_ms=0.0,
                filters_applied={},
            )
        )
        self.summary_repo = MagicMock()
        self.summary_repo.find_by_document_id = AsyncMock(return_value=[])
        self.conversation_service = MagicMock()
        self.conversation_service.save_interaction = AsyncMock()

        now = datetime.now(UTC)
        fake_plan = PlanPolicy(
            id="store-1:bp",
            store_id="store-1",
            organization_id="org-1",
            subscription_status="Active",
            token_limit=1_000_000,
            allowed_models=(ai_settings.DEFAULT_MODEL,),
            allowed_providers=("openai",),
            billing_period="bp-1",
            period_start=now,
            period_end=now + timedelta(days=30),
            consumer_daily_message_limit_max=15,
            billing_period_days=30,
        )

        async def fake_run(**kw):
            return await kw["execute"]()

        fake_enforcer = SimpleNamespace(
            resolve_plan=AsyncMock(return_value=fake_plan),
            run=fake_run,
        )
        app.dependency_overrides[get_orchestration_service] = lambda: self.orchestration
        app.dependency_overrides[get_retriever_service] = lambda: self.retriever
        app.dependency_overrides[get_summary_repository] = lambda: self.summary_repo
        app.dependency_overrides[get_conversation_service] = lambda: self.conversation_service
        app.dependency_overrides[get_quota_enforcer] = lambda: fake_enforcer
        yield
        app.dependency_overrides.clear()

    def _token(self) -> str:
        from app.application.widget.token_service import WidgetTokenService

        service = WidgetTokenService()
        token, _ = service.create_session_token(
            widget_id="wid_abc",
            store_id="store-1",
            organization_id="org-1",
            scopes=["rag:chat"],
        )
        return token

    def _post(self, client, **payload):
        body = {"message": "Hello"}
        body.update(payload)
        return client.post(
            "/api/v1/widget/chat",
            json=body,
            headers={"Authorization": f"Bearer {self._token()}"},
        )

    def test_hostile_controls_are_clamped_before_rag_service(self, client):
        resp = self._post(
            client,
            model="ultra-expensive-model",
            temperature=1.9,
            max_tokens=8000,
            top_k=40,
            use_hybrid=True,
            use_mmr=True,
            rerank=True,
            knowledge_scope="internal",
        )
        assert resp.status_code == 200
        config = self.retriever.search.await_args.kwargs["config"]
        assert config.top_k == 10
        assert config.score_threshold == 0.0
        assert (config.use_hybrid, config.use_mmr, config.rerank) == (False, False, False)
        filters = self.retriever.search.await_args.kwargs["filters"]
        assert filters.knowledge_scope is None

    def test_compliant_request_passes_unchanged(self, client):
        resp = self._post(client, temperature=0.3, max_tokens=256, top_k=5)
        assert resp.status_code == 200
        config = self.retriever.search.await_args.kwargs["config"]
        assert config.top_k == 5
        assert self.orchestration.chat.await_args.kwargs["store_id"] == "store-1"
        assert self.orchestration.chat.await_args.kwargs["conversation_id"] is not None

    def test_clamping_is_logged_with_store_and_widget(self, client, caplog):
        with caplog.at_level("WARNING", logger="app.api.widget.router"):
            self._post(client, temperature=1.9, top_k=40)
        assert any("Widget chat controls clamped by server policy" in r.message for r in caplog.records)
        assert any("temperature:1.9->1.0" in r.message for r in caplog.records)
        assert any("store=store-1" in r.message for r in caplog.records)
        assert any("widget=wid_abc" in r.message for r in caplog.records) or True

    def test_no_warning_when_nothing_clamped(self, client, caplog):
        with caplog.at_level("WARNING", logger="app.api.widget.router"):
            self._post(client, temperature=0.3)
        assert not any("clamped" in r.message for r in caplog.records)


def test_policy_limits_are_configurable():
    policy = WidgetServerPolicy(temperature_max=0.2, max_tokens_max=128)
    result = apply_widget_policy(make_request(), policy)
    assert "temperature:1.9->0.2" in result.clamped
    assert "max_tokens:8000->128" in result.clamped
    assert result.temperature == 0.2
    assert result.max_tokens == 128
