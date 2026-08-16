from fastapi import Request

from app.application.rag.resolver import TenantContextResolver
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.infrastructure.mongodb.repositories.business_summary_repository import BusinessSummaryRepository


def get_tenant_context(request: Request) -> TenantContext | None:
    """Resolve the authoritative tenant context from the authenticated request.

    Returns None in anonymous mode (no token or token without tenant claims);
    callers then fall back to client-supplied tenant identifiers. A token that
    carries only a partial tenant identity (e.g. org without store) is treated
    as unbound (None) — callers must reject rather than trust client input.
    """
    import logging

    logger = logging.getLogger(__name__)
    claims = {
        "organization_id": getattr(request.state, "organization_id", None),
        "store_id": getattr(request.state, "store_id", None),
        "request_id": getattr(request.state, "request_id", ""),
    }
    if not claims["organization_id"] and not claims["store_id"]:
        return None
    try:
        return TenantContextResolver.from_claims(claims)
    except ValueError as exc:
        logger.warning("Partial tenant claims ignored: %s", exc)
        return None


def get_summary_repository() -> BusinessSummaryRepository:
    return BusinessSummaryRepository()
