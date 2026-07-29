import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from app.middleware.rate_limit import RateLimitMiddleware

@patch("app.middleware.rate_limit.Redis")
def test_rate_limit_middleware_redis_success(mock_redis_cls):
    # Mock Redis client and its pipeline
    mock_pipeline = MagicMock()
    # First request: returns count=1
    # Second request: returns count=2
    # Third request: returns count=3 (which exceeds limit of 2)
    mock_pipeline.execute = AsyncMock(side_effect=[[1, True], [2, True], [3, True]])
    
    mock_redis = MagicMock()
    mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
    mock_redis_cls.from_url.return_value = mock_redis

    app = FastAPI()
    
    @app.get("/test")
    def test_route():
        return {"status": "ok"}

    app.add_middleware(
        RateLimitMiddleware, 
        limit_per_minute=2, 
        whitelist_paths=("/health",)
    )
    
    client = TestClient(app)
    
    # First request -> Allowed
    resp1 = client.get("/test")
    assert resp1.status_code == 200
    assert resp1.headers["X-RateLimit-Limit"] == "2"
    assert resp1.headers["X-RateLimit-Remaining"] == "1"
    
    # Second request -> Allowed
    resp2 = client.get("/test")
    assert resp2.status_code == 200
    assert resp2.headers["X-RateLimit-Remaining"] == "0"
    
    # Third request -> Blocked
    resp3 = client.get("/test")
    assert resp3.status_code == 429
    assert resp3.json()["detail"] == "Rate limit exceeded. Please try again later."


@patch("app.middleware.rate_limit.Redis")
def test_rate_limit_middleware_memory_fallback(mock_redis_cls):
    # Force Redis connection to raise exception to trigger memory fallback
    mock_redis_cls.from_url.side_effect = Exception("Redis connection failed")

    app = FastAPI()
    
    @app.get("/test")
    def test_route():
        return {"status": "ok"}
        
    @app.get("/health")
    def health_route():
        return {"status": "ok"}

    app.add_middleware(
        RateLimitMiddleware, 
        limit_per_minute=2, 
        whitelist_paths=("/health",)
    )
    
    client = TestClient(app)
    
    # 1. Whitelisted route passes regardless
    for _ in range(5):
        response = client.get("/health")
        assert response.status_code == 200
    
    # Use headers to specify a unique client IP to ensure isolation
    headers = {"X-Forwarded-For": "192.168.1.99"}

    # 2. Rate limited route
    # First request
    resp1 = client.get("/test", headers=headers)
    assert resp1.status_code == 200
    assert resp1.headers["X-RateLimit-Limit"] == "2"
    assert resp1.headers["X-RateLimit-Remaining"] == "1"
    
    # Second request
    resp2 = client.get("/test", headers=headers)
    assert resp2.status_code == 200
    assert resp2.headers["X-RateLimit-Remaining"] == "0"
    
    # Third request -> Blocked with 429
    resp3 = client.get("/test", headers=headers)
    assert resp3.status_code == 429
    assert resp3.json()["detail"] == "Rate limit exceeded. Please try again later."
    assert "Retry-After" in resp3.headers
