import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.analytics_router import router as admin_analytics_router
from app.api.admin.prompt_router import router as admin_prompt_router
from app.api.admin.router import router as admin_router
from app.api.ai.router import router as ai_router
from app.api.analytics.router import router as analytics_router
from app.api.auth.router import router as auth_router
from app.api.chat.router import router as chat_router
from app.api.commerce.router import router as commerce_router
from app.api.integration.router import router as integration_router
from app.api.knowledge.generation_router import router as knowledge_generation_router
from app.api.knowledge.job_router import router as knowledge_job_router
from app.api.knowledge.retrieval_router import router as knowledge_retrieval_router
from app.api.knowledge.unified_router import router as knowledge_unified_router
from app.api.recommendation.router import router as recommendation_router
from app.api.ticket.router import router as ticket_router
from app.api.widget.admin_router import router as widget_admin_router
from app.api.widget.router import router as widget_router
from app.api.widget.static_router import router as widget_static_router
from app.application.admin.services.prompt_service import PromptService
from app.core.ai_exceptions import AIException
from app.core.config import settings
from app.core.exception_handlers import (
    ai_exception_handler,
    domain_exception_handler,
    infrastructure_exception_handler,
    unhandled_exception_handler,
)
from app.core.exceptions import DomainException, InfrastructureException
from app.middleware.audit import AuditMiddleware
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import AITracingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.widget_cors import WidgetCorsMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        from app.infrastructure.mongodb import ensure_knowledge_upload_indexes
        from app.infrastructure.mongodb.client import MongoClientManager

        db = MongoClientManager.get_database()
        if db is not None:
            await ensure_knowledge_upload_indexes(db)
    except Exception:
        logger.warning("Could not reconcile knowledge_uploads indexes at startup", exc_info=True)

    try:
        service = PromptService()
        count = await service.seed_defaults()
        if count:
            logger.info("Seeded %d default prompts", count)
    except Exception:
        pass
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_exception_handler(DomainException, domain_exception_handler)
app.add_exception_handler(InfrastructureException, infrastructure_exception_handler)
app.add_exception_handler(AIException, ai_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Correlation-ID",
    ],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
        "X-Correlation-ID",
    ],
    max_age=3600,
)
# `app.add_middleware` inserts at index 0, so the LAST registration is the OUTERMOST.
# RequestContextMiddleware must be outermost: every downstream middleware (auth,
# tracing, widget CORS) and every handler observes the same request_id.
app.add_middleware(RequestContextMiddleware)
app.add_middleware(WidgetCorsMiddleware)
app.add_middleware(AITracingMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
    llm_limit_per_minute=settings.RATE_LIMIT_LLM_PER_MINUTE,
    widget_bootstrap_limit_per_minute=settings.RATE_LIMIT_WIDGET_BOOTSTRAP_PER_MINUTE,
    widget_session_limit_per_minute=settings.RATE_LIMIT_WIDGET_SESSION_PER_MINUTE,
)
app.add_middleware(AuthMiddleware)
app.add_middleware(AuditMiddleware)
# app.add_middleware(CORSMiddleware)

app.include_router(analytics_router)
app.include_router(integration_router)
app.include_router(chat_router)
app.include_router(ai_router)
app.include_router(commerce_router)
app.include_router(knowledge_generation_router)
app.include_router(knowledge_retrieval_router)
app.include_router(knowledge_job_router)
app.include_router(knowledge_unified_router)
app.include_router(recommendation_router)
app.include_router(admin_analytics_router)
app.include_router(admin_prompt_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(ticket_router)
app.include_router(widget_router)
app.include_router(widget_admin_router)
app.include_router(widget_static_router)


@app.get("/health/")
def health_check():
    return {"status": "AI Service is live !"}
