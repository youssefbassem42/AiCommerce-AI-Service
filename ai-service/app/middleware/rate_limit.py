import time
import logging
from typing import Dict, Tuple, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from redis.asyncio import Redis
from app.core.config import settings

logger = logging.getLogger("ai_service")

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI/Starlette middleware for API rate limiting.
    Uses Redis as the primary database for rate limit tracking.
    Falls back to a thread-safe local in-memory store if Redis is unavailable.
    """

    def __init__(
        self,
        app,
        limit_per_minute: int = 100,
        whitelist_paths: Tuple[str, ...] = ("/health/", "/health"),
    ):
        super().__init__(app)
        self.limit_per_minute = limit_per_minute
        self.whitelist_paths = whitelist_paths
        
        # Local in-memory fallback store: {ip_address: [(timestamp)]}
        self.local_store: Dict[str, list] = {}
        
        # Redis client initialization (lazy connection)
        self.redis: Optional[Redis] = None
        try:
            self.redis = Redis.from_url(settings.REDIS_SETTINGS.REDIS_URL, decode_responses=True)
            logger.info("RateLimitMiddleware: Redis client initialized successfully.")
        except Exception as e:
            logger.error(f"RateLimitMiddleware: Failed to initialize Redis client: {e}")

    async def _is_rate_limited_redis(self, client_ip: str) -> Tuple[bool, int, int]:
        """
        Check rate limit using Redis (fixed window of 60 seconds).
        Returns (is_limited, remaining, reset_time_seconds).
        """
        if not self.redis:
            raise ValueError("Redis client not initialized")

        current_time = int(time.time())
        window_start = current_time // 60
        key = f"rate_limit:{client_ip}:{window_start}"

        try:
            # Multi-exec transaction to increment count and set TTL
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, 60)
                results = await pipe.execute()

            request_count = results[0]
            remaining = max(0, self.limit_per_minute - request_count)
            reset_time = 60 - (current_time % 60)

            is_limited = request_count > self.limit_per_minute
            return is_limited, remaining, reset_time

        except Exception as e:
            logger.warning(f"RateLimitMiddleware: Redis check failed, falling back to memory. Error: {e}")
            raise e

    def _is_rate_limited_memory(self, client_ip: str) -> Tuple[bool, int, int]:
        """
        In-memory fallback rate limiting (sliding window of 60 seconds).
        Returns (is_limited, remaining, reset_time_seconds).
        """
        current_time = time.time()
        
        # Initialize or cleanup old requests
        if client_ip not in self.local_store:
            self.local_store[client_ip] = []
            
        # Keep only requests within the last 60 seconds
        self.local_store[client_ip] = [
            t for t in self.local_store[client_ip] if current_time - t < 60
        ]
        
        request_count = len(self.local_store[client_ip])
        
        if request_count >= self.limit_per_minute:
            # Limited. The oldest request in the window dictates the reset
            reset_time = int(60 - (current_time - self.local_store[client_ip][0]))
            return True, 0, reset_time

        # Allow request
        self.local_store[client_ip].append(current_time)
        remaining = self.limit_per_minute - (request_count + 1)
        reset_time = 60
        return False, remaining, reset_time

    def _get_rate_limit_key(self, request: Request) -> str:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return f"tenant:{tenant_id}"
        client_ip = request.client.host if request.client else "unknown-ip"
        return f"ip:{client_ip}"

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.whitelist_paths:
            return await call_next(request)

        rate_limit_key = self._get_rate_limit_key(request)

        is_limited = False
        remaining = self.limit_per_minute
        reset_time = 60

        if self.redis:
            try:
                is_limited, remaining, reset_time = await self._is_rate_limited_redis(rate_limit_key)
            except Exception:
                is_limited, remaining, reset_time = self._is_rate_limited_memory(rate_limit_key)
        else:
            is_limited, remaining, reset_time = self._is_rate_limited_memory(rate_limit_key)

        if is_limited:
            logger.warning(f"RateLimitMiddleware: Rate limit exceeded for key: {rate_limit_key}. Reset in {reset_time}s.")
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "limit": self.limit_per_minute,
                    "reset_seconds": reset_time
                }
            )
            response.headers["Retry-After"] = str(reset_time)
            response.headers["X-RateLimit-Limit"] = str(self.limit_per_minute)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(reset_time)
            return response

        # Process the request
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response
