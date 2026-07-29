import pytest


@pytest.mark.unit
class TestMiddlewareImports:
    def test_audit_middleware_imports(self):
        from app.middleware.audit import AuditMiddleware
        assert AuditMiddleware is not None

    def test_auth_middleware_imports(self):
        from app.middleware.auth import AuthMiddleware
        assert AuthMiddleware is not None

    def test_logging_middleware_imports(self):
        from app.middleware.logging import AITracingMiddleware
        assert AITracingMiddleware is not None

    def test_rate_limit_middleware_imports(self):
        from app.middleware.rate_limit import RateLimitMiddleware
        assert RateLimitMiddleware is not None


@pytest.mark.unit
class TestCoreImports:
    def test_config_imports(self):
        from app.core.config import Settings, get_settings, settings
        assert Settings is not None
        assert settings is not None

    def test_main_app_imports(self):
        from app.main import app
        assert app is not None
        assert app.title == "AI Commerce Platform"

    def test_health_endpoint(self):
        from app.main import app
        from fastapi.routing import APIRoute
        routes = [r.path for r in app.routes if isinstance(r, APIRoute)]
        assert "/health/" in routes
