"""Static CDN widget routes: versioned assets, cache headers, snippet builder."""

import pytest
from fastapi.testclient import TestClient

from app.api.widget.admin_router import build_install_snippet
from app.middleware.auth import WHITELIST_PATHS
from app.middleware.rate_limit import WIDGET_CDN_PREFIX


@pytest.fixture(scope="module")
def client():
    from app.main import app

    return TestClient(app)


def _cache_control(response) -> str:
    return response.headers.get("cache-control", "")


class TestVersionedRoutes:
    def test_legacy_widget_script_is_served(self, client):
        resp = client.get("/widget.js")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/javascript")
        assert "public" in _cache_control(resp)

    def test_v1_loader_is_served(self, client):
        resp = client.get("/widget/v1/widget.js")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/javascript")
        assert "must-revalidate" in _cache_control(resp)

    def test_v1_runtime_is_served(self, client):
        resp = client.get("/widget/v1/runtime.js")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/javascript")

    def test_v1_hashed_runtime_is_served_immutable(self, client):
        resp = client.get("/widget/v1/runtime.f99dc960d61c.js")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/javascript")
        assert "immutable" in _cache_control(resp)
        assert "max-age=31536000" in _cache_control(resp)

    def test_v1_hashed_runtime_rejects_unknown_hashes(self, client):
        assert client.get("/widget/v1/runtime.zzz.js").status_code == 404
        assert client.get("/widget/v1/runtime.1234567890ab.js").status_code == 404

    def test_v1_loader_and_hashed_runtime_are_whitelisted(self):
        assert "/widget/v1/widget.js" in WHITELIST_PATHS
        assert "/widget/v1/runtime.js" in WHITELIST_PATHS
        assert WIDGET_CDN_PREFIX == "/widget/v1/"

    def test_demo_page_still_served(self, client):
        resp = client.get("/demo")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")


class TestInstallSnippet:
    def test_snippet_points_at_request_origin_and_v1_loader(self):
        snippet = build_install_snippet("https://merchant.example.com/", "wi_abc")
        assert (
            snippet
            == '<script src="https://merchant.example.com/widget/v1/widget.js" data-widget-key="wi_abc"></script>'
        )

    def test_snippet_handles_origin_without_trailing_slash(self):
        snippet = build_install_snippet("https://localhost:8000", "wk_live_key")
        assert "https://localhost:8000/widget/v1/widget.js" in snippet

    def test_snippet_never_embeds_secrets(self):
        snippet = build_install_snippet("https://merchant.example.com", "wi_publickey")
        assert "Bearer" not in snippet
        assert "access_token" not in snippet
