from fastapi import Depends, HTTPException, Request, status

from app.application.widget.bootstrap_service import WidgetBootstrapService
from app.application.widget.cached_origin_service import CachedWidgetOriginService
from app.application.widget.installation_service import WidgetInstallationService
from app.application.widget.token_service import WidgetTokenService, widget_token_service
from app.core.security import ERR_INSUFFICIENT, ERR_INVALID_FORMAT, ERR_MISSING_HEADER
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetInstallationRepository,
)
from app.infrastructure.mongodb.repositories.widget_installation_repository import (
    WidgetInstallationMongoRepository,
)

_widget_origin_cache: CachedWidgetOriginService | None = None


def get_widget_installation_repository() -> WidgetInstallationRepository:
    return WidgetInstallationMongoRepository()


def get_widget_token_service() -> WidgetTokenService:
    return widget_token_service


def get_widget_origin_cache() -> CachedWidgetOriginService:
    global _widget_origin_cache
    if _widget_origin_cache is None:
        _widget_origin_cache = CachedWidgetOriginService(WidgetInstallationMongoRepository())
    return _widget_origin_cache


def get_widget_installation_service(
    repository: WidgetInstallationRepository = Depends(get_widget_installation_repository),
    origin_cache: CachedWidgetOriginService = Depends(get_widget_origin_cache),
) -> WidgetInstallationService:
    service = WidgetInstallationService(repository=repository)
    service.set_on_created(origin_cache.clear)
    return service


def get_widget_bootstrap_service(
    repository: WidgetInstallationRepository = Depends(get_widget_installation_repository),
    token_service: WidgetTokenService = Depends(get_widget_token_service),
    origin_cache: CachedWidgetOriginService = Depends(get_widget_origin_cache),
) -> WidgetBootstrapService:
    return WidgetBootstrapService(repository=repository, token_service=token_service, origin_cache=origin_cache)


def get_widget_tenant_context(request: Request) -> TenantContext:
    """Authoritative tenant context derived from the validated widget access token.

    The tenant is always resolved server-side from token claims; any client-supplied
    tenant identifiers are never consulted.
    """
    if getattr(request.state, "actor_type", None) != "widget":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERR_MISSING_HEADER)

    store_id = getattr(request.state, "store_id", None)
    organization_id = getattr(request.state, "organization_id", None)
    widget_id = getattr(request.state, "widget_id", None)
    if not store_id or not organization_id or not widget_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERR_INVALID_FORMAT)

    return TenantContext(
        organization_id=organization_id,
        store_id=store_id,
        widget_id=widget_id,
        actor_type="widget",
    )


def require_widget_scope(scope: str):
    """Require a scope on the validated widget access token (403 otherwise)."""

    def _require_widget_scope(request: Request) -> None:
        if getattr(request.state, "actor_type", None) != "widget":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERR_MISSING_HEADER)
        scopes = getattr(request.state, "scopes", [])
        if scope not in scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_INSUFFICIENT)

    return _require_widget_scope
