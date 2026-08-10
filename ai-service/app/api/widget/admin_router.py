from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth.dependencies import (
    get_current_organization_id,
    get_current_store_id,
    require_admin_role,
)
from app.api.widget.dependencies import get_widget_installation_service
from app.api.widget.schemas import (
    WidgetInstallationCreateRequestSchema,
    WidgetInstallationCreateResponseSchema,
    WidgetInstallationListResponseSchema,
)
from app.application.widget.installation_service import WidgetInstallationService
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetInstallationNotFoundError,
)

router = APIRouter(
    prefix="/api/v1/admin/widget-installations",
    tags=["Widget Installations"],
    dependencies=[Depends(require_admin_role)],
)


@router.post(
    "",
    response_model=WidgetInstallationCreateResponseSchema,
    status_code=201,
    summary="Provision a widget installation for the authenticated store",
)
async def create_widget_installation(
    payload: WidgetInstallationCreateRequestSchema,
    store_id: str = Depends(get_current_store_id),
    organization_id: str = Depends(get_current_organization_id),
    installation_service: WidgetInstallationService = Depends(get_widget_installation_service),
) -> WidgetInstallationCreateResponseSchema:
    installation, widget_key = await installation_service.create(
        store_id=store_id,
        organization_id=organization_id,
        environment=payload.environment,
        allowed_origins=payload.allowed_origins,
        scopes=payload.scopes,
    )
    return WidgetInstallationCreateResponseSchema(
        widget_key=widget_key,
        widget_id=installation.widget_id,
        store_id=installation.store_id,
        organization_id=installation.organization_id,
        environment=installation.environment,
        status=installation.status,
        allowed_origins=installation.allowed_origins,
        scopes=installation.scopes,
    )


@router.get(
    "",
    response_model=list[WidgetInstallationListResponseSchema],
    summary="List widget installations for the authenticated store",
)
async def list_widget_installations(
    store_id: str = Depends(get_current_store_id),
    installation_service: WidgetInstallationService = Depends(get_widget_installation_service),
) -> list[WidgetInstallationListResponseSchema]:
    installations = await installation_service.list_for_store(store_id)
    return [
        WidgetInstallationListResponseSchema(
            id=installation.id,
            widget_id=installation.widget_id,
            environment=installation.environment,
            status=installation.status,
            allowed_origins=installation.allowed_origins,
            scopes=installation.scopes,
            last_used_at=installation.last_used_at,
            created_at=installation.created_at,
        )
        for installation in installations
    ]


@router.patch(
    "/{widget_id}/disable",
    response_model=WidgetInstallationListResponseSchema,
    summary="Disable a widget installation (immediately denies bootstrap)",
)
async def disable_widget_installation(
    widget_id: str,
    store_id: str = Depends(get_current_store_id),
    installation_service: WidgetInstallationService = Depends(get_widget_installation_service),
) -> WidgetInstallationListResponseSchema:
    try:
        installation = await installation_service.disable(widget_id, store_id)
    except WidgetInstallationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget installation not found") from exc
    return WidgetInstallationListResponseSchema(
        id=installation.id,
        widget_id=installation.widget_id,
        environment=installation.environment,
        status=installation.status,
        allowed_origins=installation.allowed_origins,
        scopes=installation.scopes,
        last_used_at=installation.last_used_at,
        created_at=installation.created_at,
    )
