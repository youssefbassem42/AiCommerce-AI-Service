"""Phase D tests: endpoint-aware rate limit tiers (R-08/R-09).

Tiers:
  default          every non-whitelisted route (store or IP identity)
  llm              /chat, /api/v1/ai/chat*, /rag/chat*, /api/v1/recommendations*,
                   /api/v1/widget/chat, /api/v1/widget/recommendations
  widget_session   /api/v1/widget/chat, /api/v1/widget/recommendations (store key)
  widget_bootstrap /api/v1/widget/bootstrap (SHA-256 of X-Widget-Key)
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from starlette.responses import JSONResponse

from app.middleware.rate_limit import RateLimitMiddleware


def make_request(path="/api/v1/tickets", store_id=None, widget_key=None):
    headers = []
    if widget_key:
        headers.append((b"x-widget-key", widget_key.encode("utf-8")))
    scope = {
        "type": "http",
        "path": path,
        "method": "GET",
        "headers": headers,
        "client": ("10.0.0.1", 8000),
    }
    request = Request(scope)
    if store_id is not None:
        request.state.store_id = store_id
    return request


@pytest.fixture
def middleware():
    m = RateLimitMiddleware(
        lambda app: None,
        limit_per_minute=100,
        llm_limit_per_minute=20,
        widget_bootstrap_limit_per_minute=30,
        widget_session_limit_per_minute=60,
        widget_key_header="X-Widget-Key",
    )
    m.redis = None  # force the deterministic in-memory fallback
    return m


class TestTierResolution:
    def test_default_route_single_check(self, middleware):
        checks = middleware._resolve_checks(make_request(store_id="store-1"))
        assert checks == [("store:store-1", 100, "default")]

    def test_anonymous_default_route_ip_identity(self, middleware):
        checks = middleware._resolve_checks(make_request())
        assert checks[0][0].startswith("ip:")
        assert checks[0][1] == 100

    def test_rag_chat_gets_llm_tier(self, middleware):
        checks = middleware._resolve_checks(make_request(path="/rag/chat"))
        tiers = [t for _, _, t in checks]
        assert "llm" in tiers
        llm_limit = next(l for _, l, t in checks if t == "llm")
        assert llm_limit == 20

    def test_ai_chat_stream_gets_llm_tier(self, middleware):
        checks = middleware._resolve_checks(make_request(path="/api/v1/ai/chat/stream", store_id="s1"))
        assert ("llm:store:s1", 20, "llm") in checks

    def test_plain_chat_endpoint_gets_llm_tier(self, middleware):
        checks = middleware._resolve_checks(make_request(path="/chat", store_id="s1"))
        assert ("llm:store:s1", 20, "llm") in checks

    def test_widget_bootstrap_gets_key_tier(self, middleware):
        checks = middleware._resolve_checks(
            make_request(path="/api/v1/widget/bootstrap", widget_key="my-widget-key-123")
        )
        tiers = {t: (l, k) for k, l, t in checks}
        assert "widget_bootstrap" in tiers
        limit, key = tiers["widget_bootstrap"]
        assert limit == 30
        assert key.startswith("widgetkey:")
        assert len(key) == len("widgetkey:") + 16
        assert "my-widget-key-123" not in key  # raw key never stored

    def test_widget_bootstrap_without_key_falls_back_to_identity(self, middleware):
        checks = middleware._resolve_checks(make_request(path="/api/v1/widget/bootstrap"))
        assert all(t != "widget_bootstrap" for _, _, t in checks)

    def test_widget_chat_gets_session_and_llm_tiers(self, middleware):
        checks = middleware._resolve_checks(make_request(path="/api/v1/widget/chat", store_id="store-w"))
        tiers = {t: (k, l) for k, l, t in checks}
        assert ("widget_session:store-w", 60) in [(k, l) for k, l, _ in checks]
        assert "widget_session" in tiers
        assert "llm" in tiers
        assert "default" in tiers

    def test_widget_recommendations_gets_session_tier(self, middleware):
        checks = middleware._resolve_checks(make_request(path="/api/v1/widget/recommendations", store_id="store-w"))
        assert any(k == "widget_session:store-w" for k, _, _ in checks)

    def test_widget_key_hashes_are_distinct(self, middleware):
        c1 = middleware._resolve_checks(make_request(path="/api/v1/widget/bootstrap", widget_key="key-one"))
        c2 = middleware._resolve_checks(make_request(path="/api/v1/widget/bootstrap", widget_key="key-two"))
        k1 = next(k for k, _, t in c1 if t == "widget_bootstrap")
        k2 = next(k for k, _, t in c2 if t == "widget_bootstrap")
        assert k1 != k2


class TestDispatchEnforcement:
    async def _run(self, middleware, request):
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}, status_code=200))
        return await middleware.dispatch(request, call_next)

    async def test_llm_tier_trips_before_default(self, middleware):
        middleware.llm_limit_per_minute = 2
        req = make_request(path="/rag/chat", store_id="store-1")

        r1 = await self._run(middleware, req)
        r2 = await self._run(middleware, req)
        assert r1.status_code == 200 and r2.status_code == 200

        r3 = await self._run(middleware, req)
        assert r3.status_code == 429
        assert r3.headers["X-RateLimit-Tier"] == "llm"
        assert r3.headers["X-RateLimit-Limit"] == "2"
        assert "Retry-After" in r3.headers
        import json as jsonlib

        body = jsonlib.loads(r3.body)
        assert body["tier"] == "llm"

    async def test_widget_bootstrap_is_limited_per_key(self, middleware):
        middleware.widget_bootstrap_limit_per_minute = 2
        req = make_request(path="/api/v1/widget/bootstrap", widget_key="attacker-widget-key")

        assert (await self._run(middleware, req)).status_code == 200
        assert (await self._run(middleware, req)).status_code == 200
        r3 = await self._run(middleware, req)
        assert r3.status_code == 429
        assert r3.headers["X-RateLimit-Tier"] == "widget_bootstrap"

        # A DIFFERENT widget key is unaffected — per-key isolation (R-09).
        other = make_request(path="/api/v1/widget/bootstrap", widget_key="other-widget-key")
        assert (await self._run(middleware, other)).status_code == 200

    async def test_widget_session_trips_per_store(self, middleware):
        middleware.widget_session_limit_per_minute = 2
        req = make_request(path="/api/v1/widget/chat", store_id="store-w")

        assert (await self._run(middleware, req)).status_code == 200
        assert (await self._run(middleware, req)).status_code == 200
        r3 = await self._run(middleware, req)
        assert r3.status_code == 429
        assert r3.headers["X-RateLimit-Tier"] == "widget_session"

        # Another session (different store) is unaffected.
        other = make_request(path="/api/v1/widget/chat", store_id="store-w2")
        assert (await self._run(middleware, other)).status_code == 200

    async def test_default_tier_still_applies(self, middleware):
        middleware.limit_per_minute = 2
        req = make_request(path="/api/v1/tickets", store_id="store-1")
        assert (await self._run(middleware, req)).status_code == 200
        assert (await self._run(middleware, req)).status_code == 200
        r3 = await self._run(middleware, req)
        assert r3.status_code == 429
        assert r3.headers["X-RateLimit-Tier"] == "default"

    async def test_success_response_reports_default_tier_headers(self, middleware):
        req = make_request(path="/api/v1/tickets", store_id="store-1")
        resp = await self._run(middleware, req)
        assert resp.headers["X-RateLimit-Limit"] == "100"
        assert resp.headers["X-RateLimit-Remaining"] == "99"

    async def test_raw_widget_key_never_enters_local_store(self, middleware):
        middleware.widget_bootstrap_limit_per_minute = 2
        req = make_request(path="/api/v1/widget/bootstrap", widget_key="secret-raw-key-xyz")
        await self._run(middleware, req)
        await self._run(middleware, req)
        assert not any("secret-raw-key-xyz" in k for k in middleware.local_store)
