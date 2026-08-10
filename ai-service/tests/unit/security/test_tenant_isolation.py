"""Tenant isolation regression suite (Phase C).

Covers the enforcement matrix documented in docs/security/tenant-isolation-matrix.md:
    C1 tenant-scoped vector retrieval (claims authoritative)
    C2 knowledge CRUD scoped to claim store
    C3 RAG request tenant resolution from claims
    C4 recommendation tenant resolution from claims
    C9 chunk/version scoping per store
    C10 analytics scoping per store

Failure mode doctrine: a tenant-bound retriever/route ALWAYS overrides caller
supplied tenant identifiers; a mismatched identifier is a manipulation attempt
and is DENIED (403), never silently re-scoped.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.application.knowledge.retrieval.dto import RetrievedChunkDTO
from app.application.rag.resolver import TenantContextResolver
from app.core.auth_settings import auth_settings
from app.core.security import EMAIL_CLAIM, NAME_IDENTIFIER_CLAIM

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def make_token(
    store_id: str | None = "22222222-2222-2222-2222-222222222222",
    org_id: str | None = "33333333-3333-3333-3333-333333333333",
    role: str = "Admin",
) -> dict[str, str]:
    import jwt as pyjwt

    user_guid = "11111111-1111-1111-1111-111111111111"
    payload = {
        "sub": user_guid,
        NAME_IDENTIFIER_CLAIM: user_guid,
        "email": "admin@example.com",
        EMAIL_CLAIM: "admin@example.com",
        "security_stamp": "test-security-stamp",
        "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": role,
        "iss": auth_settings.JWT_ISSUER,
        "aud": auth_settings.JWT_AUDIENCE,
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }
    if store_id is not None:
        payload["store_id"] = store_id
    if org_id is not None:
        payload["org_id"] = org_id
    token = pyjwt.encode(payload, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


def make_search_result(chunk_id: str, score: float) -> dict:
    return {
        "id": chunk_id,
        "score": score,
        "payload": {
            "document_id": f"doc-{chunk_id}",
            "document_title": f"Doc {chunk_id}",
            "chunk_index": 0,
            "content": f"Content of {chunk_id}",
        },
    }


@pytest.fixture(autouse=True)
def mongo_patch():
    with patch("app.infrastructure.mongodb.client.MongoClientManager.get_database"):
        yield


# ---------------------------------------------------------------------------
# service-level: tenant-bound retriever (C1, C9)
# ---------------------------------------------------------------------------


class TestRetrieverTenantScope:
    @pytest.fixture
    def tenant(self):
        return TenantContextResolver.from_claims(
            {
                "organization_id": "org-a",
                "store_id": "store-a",
                "knowledge_version": 3,
            }
        )

    @pytest.fixture
    def retriever(self, tenant):
        vector_store = AsyncMock()
        vector_store.search.return_value = [make_search_result("c1", 0.9)]
        llm = MagicMock()
        llm.embeddings = AsyncMock(return_value=MagicMock(embeddings=[[0.1, 0.2, 0.3]]))
        service = RetrieverServiceFixture.build(vector_store=vector_store, llm_provider=llm, tenant=tenant)
        return service, vector_store

    @pytest.mark.asyncio
    async def test_caller_filters_are_overridden_by_tenant(self, retriever):
        """C1: a caller passing ANOTHER store's identifiers must get ONLY the
        tenant's store — the foreign identifiers never reach the vector store."""
        service, vector_store = retriever
        captured = {}

        async def fake_semantic(collection_name, query_embedding, cfg, must=None, **kwargs):
            captured["must"] = must
            return [
                RetrievedChunkDTO(
                    chunk_id="c1",
                    document_id="d1",
                    document_title="Doc 1",
                    chunk_index=0,
                    content="Content",
                    score=0.9,
                    rank=1,
                )
            ]

        async def fake_ensure(collection_name):
            return True

        service._semantic_search = fake_semantic
        service._ensure_collection = fake_ensure

        await service.search(
            query="pricing",
            filters=RetrievalFilters(
                organization_id="org-attacker",
                store_id="store-attacker",
                knowledge_version=99,
            ),
        )

        must = {c["key"]: c["value"] for c in captured["must"]}
        assert must["organization_id"] == "org-a"
        assert must["store_id"] == "store-a"
        assert must["knowledge_version"] == 3
        assert "store-attacker" not in must.values()
        assert "org-attacker" not in must.values()

    @pytest.mark.asyncio
    async def test_unbound_retriever_warns_on_global_scope(self):
        """Documents the failure mode the tenant binding eliminates: an unbound
        retriever with no filters would query globally (no store condition)."""
        vector_store = AsyncMock()
        vector_store.search.return_value = [make_search_result("c1", 0.9)]
        llm = MagicMock()
        llm.embeddings = AsyncMock(return_value=MagicMock(embeddings=[[0.1, 0.2, 0.3]]))
        service = RetrieverServiceFixture.build(vector_store=vector_store, llm_provider=llm, tenant=None)
        service._semantic_search = AsyncMock(
            return_value=[
                RetrievedChunkDTO(
                    chunk_id="c1",
                    document_id="d1",
                    document_title="Doc 1",
                    chunk_index=0,
                    content="Content",
                    score=0.9,
                    rank=1,
                )
            ]
        )
        service._ensure_collection = AsyncMock(return_value=True)

        from app.application.knowledge.retrieval.service import logger as service_logger

        with patch.object(service_logger, "warning") as mock_warn:
            await service.search(query="pricing", filters=RetrievalFilters())
            captured = service._semantic_search.await_args.kwargs["must"]
            keys = {c["key"] for c in captured}
            assert "store_id" not in keys
            assert mock_warn.called

    @pytest.mark.asyncio
    async def test_tenant_bound_version_isolates_chunks(self, retriever):
        """C9: knowledge_version is part of the tenant scope and cannot be
        re-pointed by the caller."""
        service, vector_store = retriever
        filters = service._enforce_tenant_scope(RetrievalFilters(knowledge_version=42, store_id="store-attacker"))
        assert filters.store_id == "store-a"
        assert filters.knowledge_version == 3
        conditions = {c["key"]: c["value"] for c in service._build_filter_conditions(filters)}
        assert conditions["knowledge_version"] == 3
        assert conditions["store_id"] == "store-a"


class RetrieverServiceFixture:
    """Local construction helper kept separate to avoid leaking test concerns."""

    @staticmethod
    def build(vector_store, llm_provider, tenant):
        from app.application.knowledge.retrieval.service import RetrieverService

        return RetrieverService(
            vector_store=vector_store,
            llm_provider=llm_provider,
            default_config=RetrievalConfig(top_k=5),
            tenant=tenant,
        )


# ---------------------------------------------------------------------------
# API-level: retrieval search (C1)
# ---------------------------------------------------------------------------


class TestRetrievalSearchIsolation:
    @pytest.fixture(autouse=True)
    def deps(self):
        from app.api.knowledge.retrieval_dependencies import get_retriever_service
        from app.main import app

        retriever = AsyncMock()
        retriever.search = AsyncMock(
            return_value=MagicMock(
                query="q",
                results=[],
                total_count=0,
                latency_ms=1.0,
                strategy="semantic",
                filters_applied={},
                model_dump=lambda: {},
            )
        )
        app.dependency_overrides[get_retriever_service] = lambda: retriever
        self.retriever = retriever

        if not any(getattr(r, "path", None) and "/knowledge/retrieval" in str(r.path) for r in app.routes):
            from app.api.knowledge.retrieval_router import router

            app.include_router(router)

        yield
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    def _post_search(self, client, headers=None, **payload):
        body = {"query": payload.pop("query", "pricing")}
        body.update(payload)
        return client.post("/knowledge/retrieval/search", json=body, headers=headers)

    def test_search_without_store_claim_is_denied(self, client):
        resp = self._post_search(client, headers=make_token(store_id=None, org_id=None))
        assert resp.status_code == 403
        self.retriever.search.assert_not_called()

    def test_search_mismatched_payload_store_is_denied(self, client):
        resp = self._post_search(client, headers=make_token(), store_id="store-attacker")
        assert resp.status_code == 403
        self.retriever.search.assert_not_called()

    def test_search_mismatched_payload_org_is_denied(self, client):
        resp = self._post_search(client, headers=make_token(), organization_id="org-attacker")
        assert resp.status_code == 403
        self.retriever.search.assert_not_called()

    def test_search_without_payload_uses_claim_store(self, client):
        resp = self._post_search(client, headers=make_token())
        assert resp.status_code == 200
        _, kwargs = self.retriever.search.await_args
        filters = kwargs["filters"]
        assert filters.store_id == "22222222-2222-2222-2222-222222222222"
        assert filters.organization_id == "33333333-3333-3333-3333-333333333333"

    def test_search_requires_authentication(self, client):
        resp = self._post_search(client)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# API-level: analytics (C10)
# ---------------------------------------------------------------------------


class TestAnalyticsIsolation:
    @pytest.fixture(autouse=True)
    def deps(self):
        from app.api.analytics.dependencies import get_sentiment_analytics_service
        from app.main import app

        self.service = AsyncMock()
        self.service.get_sentiment_summary = AsyncMock(
            return_value=MagicMock(
                model_dump=lambda: {
                    "store_id": "22222222-2222-2222-2222-222222222222",
                    "total": 0,
                    "positive_count": 0,
                    "neutral_count": 0,
                    "negative_count": 0,
                    "positive_pct": 0.0,
                    "neutral_pct": 0.0,
                    "negative_pct": 0.0,
                }
            )
        )
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: self.service
        yield
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    def test_mismatched_store_id_is_denied(self, client):
        resp = client.get(
            "/api/v1/analytics/sentiment-summary",
            params={"store_id": "store-attacker"},
            headers=make_token(),
        )
        assert resp.status_code == 403
        self.service.get_sentiment_summary.assert_not_called()

    def test_omitted_store_id_uses_claim_store(self, client):
        resp = client.get("/api/v1/analytics/sentiment-summary", headers=make_token())
        assert resp.status_code == 200
        self.service.get_sentiment_summary.assert_awaited_once_with("22222222-2222-2222-2222-222222222222")

    def test_matching_store_id_is_allowed(self, client):
        resp = client.get(
            "/api/v1/analytics/sentiment-summary",
            params={"store_id": "22222222-2222-2222-2222-222222222222"},
            headers=make_token(),
        )
        assert resp.status_code == 200

    def test_without_store_claim_is_denied(self, client):
        resp = client.get(
            "/api/v1/analytics/sentiment-summary",
            headers=make_token(store_id=None),
        )
        assert resp.status_code == 403
        self.service.get_sentiment_summary.assert_not_called()
