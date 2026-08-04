from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.ai_exceptions import AIException, ProviderNotFoundException
from app.core.exception_handlers import (
    ai_exception_handler,
    domain_exception_handler,
    infrastructure_exception_handler,
    unhandled_exception_handler,
)
from app.core.exceptions import DomainException, EntityNotFoundException, InfrastructureException
from app.domain.job.exceptions import JobNotFoundException
from app.domain.knowledge.exceptions import (
    DuplicateUploadException,
    KnowledgeDocumentNotFoundException,
)


def make_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(InfrastructureException, infrastructure_exception_handler)
    app.add_exception_handler(AIException, ai_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/domain-error")
    def domain_error():
        raise KnowledgeDocumentNotFoundException("Document 'd1' not found")

    @app.get("/entity-error")
    def entity_error():
        raise EntityNotFoundException("product", "p1")

    @app.get("/conflict-error")
    def conflict_error():
        raise DuplicateUploadException("File already uploaded")

    @app.get("/job-error")
    def job_error():
        raise JobNotFoundException("Job 'j1' not found")

    @app.get("/infra-error")
    def infra_error():
        raise InfrastructureException("Database unreachable")

    @app.get("/ai-error")
    def ai_error():
        raise ProviderNotFoundException("openai")

    @app.get("/unexpected")
    def unexpected_error():
        raise RuntimeError("secret internal detail")

    return app


def test_domain_error_envelope_and_status():
    client = TestClient(make_app())
    resp = client.get("/domain-error")
    assert resp.status_code == 404
    assert resp.json() == {
        "code": "KnowledgeDocumentNotFoundException",
        "message": "Document 'd1' not found",
        "details": None,
    }


def test_entity_not_found_maps_to_404():
    client = TestClient(make_app())
    resp = client.get("/entity-error")
    assert resp.status_code == 404
    assert resp.json()["code"] == "EntityNotFoundException"


def test_conflict_status_code():
    client = TestClient(make_app())
    resp = client.get("/conflict-error")
    assert resp.status_code == 409
    assert resp.json()["code"] == "DuplicateUploadException"


def test_job_not_found_inherits_404():
    client = TestClient(make_app())
    resp = client.get("/job-error")
    assert resp.status_code == 404
    assert resp.json()["code"] == "JobNotFoundException"


def test_infrastructure_error_status_and_envelope():
    client = TestClient(make_app())
    resp = client.get("/infra-error")
    assert resp.status_code == 503
    assert resp.json() == {
        "code": "InfrastructureException",
        "message": "Database unreachable",
        "details": None,
    }


def test_ai_error_uses_its_status_code():
    client = TestClient(make_app())
    resp = client.get("/ai-error")
    assert resp.status_code == 404
    assert resp.json()["code"] == "ProviderNotFoundException"


def test_unexpected_error_does_not_leak_internals():
    client = TestClient(make_app(), raise_server_exceptions=False)
    resp = client.get("/unexpected")
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "internal_error"
    assert body["message"] == "Internal server error"
    assert "secret internal detail" not in body["message"]
