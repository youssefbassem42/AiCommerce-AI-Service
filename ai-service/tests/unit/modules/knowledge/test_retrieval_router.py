import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.knowledge.retrieval.dto import UnifiedRetrievalResult, RetrievedChunkDTO


@pytest.fixture(autouse=True)
def mongo_patch():
    with patch("app.infrastructure.mongodb.client.MongoClientManager.get_database") as mock:
        yield


@pytest.fixture
def mock_retriever():
    r = AsyncMock()
    r.search = AsyncMock()
    return r


@pytest.fixture(autouse=True)
def override_deps(mock_retriever):
    from app.main import app
    from app.api.knowledge.retrieval_dependencies import get_retriever_service

    app.dependency_overrides.clear()
    app.dependency_overrides[get_retriever_service] = lambda: mock_retriever

    if not any(getattr(r, 'path', None) and "/knowledge/retrieval" in str(r.path) for r in app.routes):
        from app.api.knowledge.retrieval_router import router
        app.include_router(router)

    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


class TestRetrievalRouterSearch:
    def test_search_success(self, client, mock_retriever):
        result = UnifiedRetrievalResult(
            query="test query",
            results=[
                RetrievedChunkDTO(
                    chunk_id="c1", document_id="d1", document_title="Doc 1",
                    chunk_index=0, content="Test content", score=0.95, rank=1,
                    metadata={"language": "en"}, language="en", source_type="manual",
                ),
            ],
            total_count=1,
            strategy="semantic",
            latency_ms=42.0,
            filters_applied={"store_id": "store-1"},
        )
        mock_retriever.search.return_value = result

        resp = client.post("/knowledge/retrieval/search", json={
            "query": "test query",
            "top_k": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test query"
        assert data["strategy"] == "semantic"
        assert len(data["results"]) == 1
        assert data["results"][0]["chunk_id"] == "c1"
        assert data["results"][0]["score"] == 0.95

    def test_search_with_all_filters(self, client, mock_retriever):
        result = UnifiedRetrievalResult(
            query="filtered", results=[], total_count=0, strategy="semantic",
            latency_ms=5.0, filters_applied={"organization_id": "org-1", "store_id": "store-1", "language": "en"},
        )
        mock_retriever.search.return_value = result

        resp = client.post("/knowledge/retrieval/search", json={
            "query": "filtered",
            "organization_id": "org-1",
            "store_id": "store-1",
            "language": "en",
            "use_hybrid": True,
            "use_mmr": True,
            "rerank": True,
        })
        assert resp.status_code == 200
        assert resp.json()["filters_applied"]["organization_id"] == "org-1"

    def test_search_empty_result(self, client, mock_retriever):
        result = UnifiedRetrievalResult(
            query="empty", results=[], total_count=0, strategy="semantic",
            latency_ms=2.0, filters_applied={},
        )
        mock_retriever.search.return_value = result

        resp = client.post("/knowledge/retrieval/search", json={"query": "empty"})
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0

    def test_search_multiple_results(self, client, mock_retriever):
        result = UnifiedRetrievalResult(
            query="multi",
            results=[
                RetrievedChunkDTO(chunk_id="c1", document_id="d1", document_title="D1", chunk_index=0, content="A", score=0.9, rank=1),
                RetrievedChunkDTO(chunk_id="c2", document_id="d2", document_title="D2", chunk_index=1, content="B", score=0.8, rank=2),
            ],
            total_count=2,
            strategy="hybrid",
            latency_ms=30.0,
            filters_applied={},
        )
        mock_retriever.search.return_value = result

        resp = client.post("/knowledge/retrieval/search", json={"query": "multi"})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 2
