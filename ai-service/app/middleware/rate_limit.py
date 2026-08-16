import hashlib
import logging
import time

from fastapi import Request, Response
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger("ai_service")

WIDGET_BOOTSTRAP_PATH = "/api/v1/widget/bootstrap"
WIDGET_PREFIX = "/api/v1/widget/"

# Public static widget artifacts (embed script + demo page). No
# authentication is involved and they are cheap static files; whitelisting
# avoids charging the visitor's IP against API rate limits.
PUBLIC_STATIC_PATHS = ("/widget.js", "/demo", "/demo/")

# Cost-heavy routes: LLM generation per request. These share a tighter tier than
# the default, keyed by the same identity (store when authenticated, else IP).
LLM_PATHS = (
    "/chat",
    "/api/v1/ai/chat",
    "/api/v1/recommendations",
    "/api/v1/widget/chat",
    "/api/v1/widget/recommendations",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Endpoint-aware rate limiting (Phase D).

    A request is subject to one or more rate-limit checks, each with its own
    limit and key:

    - default tier  : every non-whitelisted route, keyed by store (JWT claim)
                      or client IP. Backward-compatible with the original
                      per-store global limiter.
    - llm tier      : cost-heavy routes (chat/rag/recommendations/widget chat),
                      same identity as the default tier.
    - widget session: POST /api/v1/widget/chat|recommendations, keyed by the
                      widget session's store_id (R-08: per-widget-session cap).
    - widget key    : POST /api/v1/widget/bootstrap, keyed by the SHA-256 hash
                      of the X-Widget-Key header (R-09: per-key cap). The raw
                      key is never stored or logged.

    If ANY check trips, the request is rejected (429) with the tripping tier's
    limits. Redis is the primary store; a bounded in-memory sliding window is
    the fallback.
    """

    def __init__(
        self,
        app,
        limit_per_minute: int = 100,
        whitelist_paths: tuple[str, ...] | None = None,
        llm_limit_per_minute: int | None = None,
        widget_bootstrap_limit_per_minute: int | None = None,
        widget_session_limit_per_minute: int | None = None,
        widget_key_header: str = "X-Widget-Key",
    ):
        super().__init__(app)
        self.limit_per_minute = limit_per_minute
        self.whitelist_paths = whitelist_paths if whitelist_paths is not None else ("/health/", "/health")
        self.llm_limit_per_minute = (
            llm_limit_per_minute if llm_limit_per_minute is not None else settings.RATE_LIMIT_LLM_PER_MINUTE
        )
        self.widget_bootstrap_limit_per_minute = (
            widget_bootstrap_limit_per_minute
            if widget_bootstrap_limit_per_minute is not None
            else settings.RATE_LIMIT_WIDGET_BOOTSTRAP_PER_MINUTE
        )
        self.widget_session_limit_per_minute = (
            widget_session_limit_per_minute
            if widget_session_limit_per_minute is not None
            else settings.RATE_LIMIT_WIDGET_SESSION_PER_MINUTE
        )
        self.widget_key_header = widget_key_header

        # Local in-memory fallback store: {rate_limit_key: [timestamps]}
        # Bounded to prevent memory exhaustion when keys are attacker-controlled.
        self.local_store: dict[str, list[float]] = {}
        self.max_local_keys = 10_000

        # Redis client initialization (lazy connection)
        self.redis: Redis | None = None
        try:
            self.redis = Redis.from_url(settings.REDIS_SETTINGS.REDIS_URL, decode_responses=True)
            logger.info("RateLimitMiddleware: Redis client initialized successfully.")
        except Exception as e:
            logger.error(f"RateLimitMiddleware: Failed to initialize Redis client: {e}")

    async def _is_rate_limited_redis(self, rate_limit_key: str, limit_per_minute: int) -> tuple[bool, int, int]:
        """
        Check rate limit using Redis (fixed window of 60 seconds).
        Returns (is_limited, remaining, reset_time_seconds).
        """
        if not self.redis:
            raise ValueError("Redis client not initialized")

        current_time = int(time.time())
        window_start = current_time // 60
        key = f"rate_limit:{rate_limit_key}:{window_start}"

        try:
            # Multi-exec transaction to increment count and set TTL
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, 60)
                results = await pipe.execute()

            request_count = results[0]
            remaining = max(0, limit_per_minute - request_count)
            reset_time = 60 - (current_time % 60)

            is_limited = request_count > limit_per_minute
            return is_limited, remaining, reset_time

        except Exception as e:
            logger.warning(f"RateLimitMiddleware: Redis check failed, falling back to memory. Error: {e}")
            raise e

    def _is_rate_limited_memory(self, rate_limit_key: str, limit_per_minute: int) -> tuple[bool, int, int]:
        """
        In-memory fallback rate limiting (sliding window of 60 seconds).
        Returns (is_limited, remaining, reset_time_seconds).
        """
        current_time = time.time()

        # Evict stale keys to keep the store bounded under high churn.
        if len(self.local_store) >= self.max_local_keys:
            stale = [k for k, times in self.local_store.items() if not times or current_time - times[-1] >= 60]
            for key in stale:
                del self.local_store[key]

        # Initialize or cleanup old requests
        if rate_limit_key not in self.local_store:
            self.local_store[rate_limit_key] = []

        # Keep only requests within the last 60 seconds
        self.local_store[rate_limit_key] = [t for t in self.local_store[rate_limit_key] if current_time - t < 60]

        request_count = len(self.local_store[rate_limit_key])

        if request_count >= limit_per_minute:
            # Limited. The oldest request in the window dictates the reset
            reset_time = int(60 - (current_time - self.local_store[rate_limit_key][0]))
            return True, 0, reset_time

        # Allow request
        self.local_store[rate_limit_key].append(current_time)
        remaining = limit_per_minute - (request_count + 1)
        reset_time = 60
        return False, remaining, reset_time

    def _get_rate_limit_key(self, request: Request) -> str:
        store_id = getattr(request.state, "store_id", None)
        if store_id:
            return f"store:{store_id}"
        client_ip = request.client.host if request.client else "unknown-ip"
        return f"ip:{client_ip}"

    def _resolve_checks(self, request: Request) -> list[tuple[str, int, str]]:
        """Resolve (key, limit, tier) checks for this request. One per tier."""
        identity = self._get_rate_limit_key(request)
        checks: list[tuple[str, int, str]] = [(identity, self.limit_per_minute, "default")]
        path = request.url.path

        if path == WIDGET_BOOTSTRAP_PATH:
            widget_key = request.headers.get(self.widget_key_header)
            if widget_key:
                digest = hashlib.sha256(widget_key.encode("utf-8")).hexdigest()[:16]
                checks.append((f"widgetkey:{digest}", self.widget_bootstrap_limit_per_minute, "widget_bootstrap"))

        if path.startswith(WIDGET_PREFIX) and path != WIDGET_BOOTSTRAP_PATH:
            store_id = getattr(request.state, "store_id", None)
            if store_id:
                checks.append((f"widget_session:{store_id}", self.widget_session_limit_per_minute, "widget_session"))

        if any(path.startswith(prefix) for prefix in LLM_PATHS):
            checks.append((f"llm:{identity}", self.llm_limit_per_minute, "llm"))

        return checks

    def _check(self, rate_limit_key: str, limit_per_minute: int) -> tuple[bool, int, int]:
        return self._is_rate_limited_memory(rate_limit_key, limit_per_minute)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.whitelist_paths or request.url.path in PUBLIC_STATIC_PATHS:
            return await call_next(request)

        checks = self._resolve_checks(request)

        default_remaining = self.limit_per_minute
        default_reset = 60
        for rate_limit_key, limit_per_minute, tier in checks:
            if self.redis:
                try:
                    is_limited, remaining, reset_time = await self._is_rate_limited_redis(
                        rate_limit_key, limit_per_minute
                    )
                except Exception:
                    is_limited, remaining, reset_time = self._is_rate_limited_memory(rate_limit_key, limit_per_minute)
            else:
                is_limited, remaining, reset_time = self._is_rate_limited_memory(rate_limit_key, limit_per_minute)

            if tier == "default":
                default_remaining, default_reset = remaining, reset_time

            if is_limited:
                logger.warning(
                    f"RateLimitMiddleware: Rate limit exceeded for key: {rate_limit_key} "
                    f"(tier={tier}). Reset in {reset_time}s."
                )
                response = JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Please try again later.",
                        "limit": limit_per_minute,
                        "reset_seconds": reset_time,
                        "tier": tier,
                    },
                )
                response.headers["Retry-After"] = str(reset_time)
                response.headers["X-RateLimit-Limit"] = str(limit_per_minute)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(reset_time)
                response.headers["X-RateLimit-Tier"] = tier
                return response

        # Process the request; report the default tier in headers (primary
        # identity limit, unchanged from the original contract).
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, default_remaining))
        response.headers["X-RateLimit-Reset"] = str(default_reset)
        return response
