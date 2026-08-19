import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder

from app.agents.integration.agent import IntegrationMappingAgent
from app.api.auth.dependencies import (
    get_current_store_id,
    get_optional_organization_id,
    require_admin_role,
)
from app.api.integration.dependencies import (
    get_ecommerce_authenticator,
    get_integration_agent,
    get_integration_service,
    get_integration_workflow,
    get_sync_orchestrator,
)
from app.api.integration.schemas import (
    AgentParseRequestSchema,
    AgentParseResponseSchema,
    AgentSyncRequestSchema,
    AgentSyncResponseSchema,
    ConnectionResponseSchema,
    CreateConnectionSchema,
    DeleteResponseSchema,
    FeatureAnalysisSchema,
    PaginatedConnectionResponseSchema,
    ParseSpecRequestSchema,
    ParseSpecResponseSchema,
    SyncRequestSchema,
    SyncResponseSchema,
    UnsupportedFeatureSchema,
    UpdateCredentialsSchema,
    UpdateMappingsSchema,
)
from app.application.integration.auth.authenticator import (
    EcommerceAuthenticator,
    discover_login_endpoint,
)
from app.application.integration.mapping.dto import (
    AuthConfigDTO,
    ConnectionCreateDTO,
    ConnectionResponseDTO,
    EntityMappingDTO,
    FieldMappingDTO,
    PaginationConfigDTO,
    ParseSpecRequestDTO,
)
from app.application.integration.mapping.services import IntegrationApplicationService
from app.application.integration.sync.orchestrator import SyncOrchestrator
from app.core.security import (
    JWTAuthenticationError,
    decode_jwt,
    get_store_admin_email_from_token,
    get_store_admin_password_from_token,
)
from app.domain.integration.exceptions import (
    IntegrationAuthenticationError,
    IntegrationConnectionNotFoundException,
)
from app.workflows.integration.graph import IntegrationWorkflow

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/integration",
    tags=["Integration"],
    dependencies=[Depends(require_admin_role)],
)


def _connection_is_owned(connection: ConnectionResponseDTO, store_id: str) -> bool:
    return bool(connection) and connection.store_id == store_id


def _extract_store_admin_credentials(request: Request) -> tuple[str, str] | None:
    """E-commerce admin email/password from the AI Commerce JWT claims.

    Returns ``None`` when the token is missing or carries no store admin
    credentials, in which case the existing (request-body credentials) flow is
    used unchanged.
    """
    auth_header = request.headers.get("authorization") or ""
    if not auth_header.lower().startswith("bearer "):
        return None
    try:
        payload = decode_jwt(auth_header[7:].strip())
    except JWTAuthenticationError:
        return None
    email = get_store_admin_email_from_token(payload)
    password = get_store_admin_password_from_token(payload)
    if not email or not password:
        return None
    return email, password


def _spec_as_dict(raw_spec: Any) -> dict | None:
    return raw_spec if isinstance(raw_spec, dict) else None


@router.post("/schemas/parse", response_model=ParseSpecResponseSchema, status_code=status.HTTP_200_OK)
async def parse_spec(
    payload: ParseSpecRequestSchema,
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> ParseSpecResponseSchema:
    dto = ParseSpecRequestDTO(
        platform_name=payload.platform_name,
        raw_spec=payload.raw_spec,
    )
    result = await service.parse_spec(dto)
    return ParseSpecResponseSchema(**result.model_dump())


@router.post("/schemas/agent-parse", response_model=AgentParseResponseSchema, status_code=status.HTTP_200_OK)
async def agent_parse_spec(
    payload: AgentParseRequestSchema,
    agent: IntegrationMappingAgent = Depends(get_integration_agent),
    store_id: str = Depends(get_current_store_id),
    organization_id: str | None = Depends(get_optional_organization_id),
) -> AgentParseResponseSchema:

    report, error, capabilities = await agent.analyze(
        raw_spec=payload.raw_spec,
        platform_name=payload.platform_name,
        store_id=store_id,
        organization_id=organization_id,
    )

    if error or report is None:
        return AgentParseResponseSchema(
            platform_name=payload.platform_name,
            base_url="",
            api_version="",
            errors=[error] if error else ["Failed to analyze specification"],
            user_friendly_error=error or "Unable to process this API specification.",
        )

    return AgentParseResponseSchema(
        platform_name=report.platform_name,
        base_url=report.base_url,
        api_version=report.api_version,
        entities=[e.model_dump() for e in report.entities],
        feature_analysis=FeatureAnalysisSchema(
            supported_features=report.feature_analysis.supported_features,
            partially_supported=report.feature_analysis.partially_supported,
            unsupported_features=[
                UnsupportedFeatureSchema(
                    feature_name=f.feature_name,
                    description=f.description,
                    reason=f.reason,
                    impact=f.impact,
                    user_message=f.user_message,
                )
                for f in report.feature_analysis.unsupported_features
            ],
            notes=report.feature_analysis.notes,
        ),
        capabilities=capabilities or {},
        warnings=report.warnings,
        errors=report.errors,
    )


@router.post("/agent-sync", response_model=AgentSyncResponseSchema, status_code=status.HTTP_200_OK)
async def agent_sync(
    payload: AgentSyncRequestSchema,
    workflow: IntegrationWorkflow = Depends(get_integration_workflow),
    store_id: str = Depends(get_current_store_id),
    organization_id: str | None = Depends(get_optional_organization_id),
) -> AgentSyncResponseSchema:
    result = await workflow.run(
        raw_spec=payload.raw_spec,
        platform_name=payload.platform_name,
        store_id=store_id,
        organization_id=organization_id,
        credentials=payload.credentials,
        connection_name=payload.name,
        auto_sync=payload.auto_sync,
    )

    if result.error or (result.sync_result and result.sync_result.get("status") == "error"):
        # A failed full integration must surface as a failure: a 200 here made
        # setup failures (bad credentials, unparseable spec, empty mappings,
        # sync errors) indistinguishable from success — the caller saw "all
        # 200 codes" while nothing was fetched or stored.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.user_friendly_error or result.error or "Integration failed.",
        )

    response = AgentSyncResponseSchema(
        connection_id=result.connection_id,
        mapping_report=result.mapping_report.model_dump() if result.mapping_report else None,
        capabilities=result.capabilities,
        sync_result=result.sync_result,
        feature_analysis=FeatureAnalysisSchema(
            supported_features=result.mapping_report.feature_analysis.supported_features,
            partially_supported=result.mapping_report.feature_analysis.partially_supported,
            unsupported_features=[
                UnsupportedFeatureSchema(
                    feature_name=f.feature_name,
                    description=f.description,
                    reason=f.reason,
                    impact=f.impact,
                    user_message=f.user_message,
                )
                for f in result.mapping_report.feature_analysis.unsupported_features
            ],
            notes=result.mapping_report.feature_analysis.notes,
        )
        if result.mapping_report
        else None,
        error=result.error,
        user_friendly_error=result.user_friendly_error,
        started_at=result.started_at.isoformat(),
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
    )
    return response


@router.post("/connections", response_model=ConnectionResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_connection(
    payload: CreateConnectionSchema,
    request: Request,
    service: IntegrationApplicationService = Depends(get_integration_service),
    orchestrator: SyncOrchestrator = Depends(get_sync_orchestrator),
    authenticator: EcommerceAuthenticator = Depends(get_ecommerce_authenticator),
    store_id: str = Depends(get_current_store_id),
    organization_id: str | None = Depends(get_optional_organization_id),
) -> ConnectionResponseSchema:
    dto = ConnectionCreateDTO(
        store_id=store_id,
        organization_id=organization_id or store_id,
        name=payload.name,
        platform_name=payload.platform_name,
        raw_spec=payload.raw_spec,
        auth_config=AuthConfigDTO(**payload.auth_config.model_dump()),
        credentials=payload.credentials,
        entity_mappings=[
            EntityMappingDTO(
                entity_type=em.entity_type,
                list_path=em.list_path,
                list_method=em.list_method,
                detail_path=em.detail_path,
                detail_method=em.detail_method,
                id_field=em.id_field,
                pagination=PaginationConfigDTO(**em.pagination.model_dump()),
                field_mappings=[FieldMappingDTO(**fm.model_dump()) for fm in em.field_mappings],
            )
            for em in payload.entity_mappings
        ],
    )

    # Sync Now flow: the AI Commerce JWT is the source of the e-commerce admin
    # credentials. When present and the submitted spec exposes a login endpoint,
    # the e-commerce login (up to 3 attempts) gates connection creation with the
    # public-data fallback:
    #   - login succeeds  -> create the connection and return 201
    #   - all attempts fail -> the connection IS still created, public data is
    #     synced (admin-protected endpoints skipped), and the response is 401
    #     with the authentication error so the admin fixes the credentials.
    credentials = _extract_store_admin_credentials(request)
    spec = _spec_as_dict(payload.raw_spec)
    replace_existing = False
    if credentials and spec is not None and discover_login_endpoint(spec):
        email, password = credentials
        replace_existing = True
        try:
            await authenticator.login(spec, email, password)
        except IntegrationAuthenticationError as e:
            created = await service.create_connection(dto, replace_existing=True)
            fallback = await orchestrator.sync_connection(created.id, auth_token=None, public_fallback=True)
            raise IntegrationAuthenticationError(
                str(e),
                details={
                    "connection_id": created.id,
                    "sync": jsonable_encoder(fallback.to_dict()),
                },
            ) from e

    result = await service.create_connection(dto, replace_existing=replace_existing)
    return ConnectionResponseSchema(**result.model_dump())


@router.get("/connections", response_model=PaginatedConnectionResponseSchema)
async def list_connections(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store_id: str = Depends(get_current_store_id),
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> PaginatedConnectionResponseSchema:
    items, total = await service.list_connections(store_id=store_id, page=page, page_size=page_size)
    return PaginatedConnectionResponseSchema(
        items=[ConnectionResponseSchema(**item.model_dump()) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/connections/{connection_id}", response_model=ConnectionResponseSchema)
async def get_connection(
    connection_id: str,
    store_id: str = Depends(get_current_store_id),
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> ConnectionResponseSchema:
    result = await service.get_connection(connection_id)
    if not _connection_is_owned(result, store_id):
        raise IntegrationConnectionNotFoundException(connection_id)
    return ConnectionResponseSchema(**result.model_dump())


@router.put("/connections/{connection_id}/mappings", response_model=ConnectionResponseSchema)
async def update_connection_mappings(
    connection_id: str,
    payload: UpdateMappingsSchema,
    store_id: str = Depends(get_current_store_id),
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> ConnectionResponseSchema:
    existing = await service.get_connection(connection_id)
    if not _connection_is_owned(existing, store_id):
        raise IntegrationConnectionNotFoundException(connection_id)
    result = await service.update_mappings(
        connection_id=connection_id,
        entity_mappings=[
            EntityMappingDTO(
                entity_type=em.entity_type,
                list_path=em.list_path,
                list_method=em.list_method,
                detail_path=em.detail_path,
                detail_method=em.detail_method,
                id_field=em.id_field,
                pagination=PaginationConfigDTO(**em.pagination.model_dump()),
                field_mappings=[FieldMappingDTO(**fm.model_dump()) for fm in em.field_mappings],
            )
            for em in payload.entity_mappings
        ],
    )
    return ConnectionResponseSchema(**result.model_dump())


@router.put("/connections/{connection_id}/credentials", response_model=ConnectionResponseSchema)
async def update_connection_credentials(
    connection_id: str,
    payload: UpdateCredentialsSchema,
    store_id: str = Depends(get_current_store_id),
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> ConnectionResponseSchema:
    existing = await service.get_connection(connection_id)
    if not _connection_is_owned(existing, store_id):
        raise IntegrationConnectionNotFoundException(connection_id)
    result = await service.update_credentials(
        connection_id=connection_id,
        auth_config_dto=AuthConfigDTO(**payload.auth_config.model_dump()),
        credentials=payload.credentials,
    )
    return ConnectionResponseSchema(**result.model_dump())


@router.post(
    "/connections/{connection_id}/sync",
    response_model=SyncResponseSchema,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_role)],
)
async def sync_connection(
    connection_id: str,
    payload: SyncRequestSchema,
    request: Request,
    store_id: str = Depends(get_current_store_id),
    orchestrator: SyncOrchestrator = Depends(get_sync_orchestrator),
    service: IntegrationApplicationService = Depends(get_integration_service),
    authenticator: EcommerceAuthenticator = Depends(get_ecommerce_authenticator),
) -> SyncResponseSchema:
    existing = await service.get_connection(connection_id)
    if not _connection_is_owned(existing, store_id):
        raise IntegrationConnectionNotFoundException(connection_id)

    # Sync Now flow: log in with the JWT-supplied admin credentials and use the
    # ephemeral token for this sync only (never stored). A failed login runs
    # the public-data fallback: public endpoints are fetched and stored,
    # admin-protected endpoints are skipped, and the response is 401 with the
    # authentication error.
    auth_token = None
    credentials = _extract_store_admin_credentials(request)
    spec = _spec_as_dict(existing.raw_spec)
    if credentials and spec is not None and discover_login_endpoint(spec):
        email, password = credentials
        try:
            auth_token = await authenticator.login(spec, email, password)
        except IntegrationAuthenticationError as e:
            fallback = await orchestrator.sync_connection(
                connection_id,
                auth_token=None,
                public_fallback=True,
                entity_types=payload.entity_types,
            )
            raise IntegrationAuthenticationError(
                str(e),
                details={"sync": jsonable_encoder(fallback.to_dict())},
            ) from e

    result = await orchestrator.sync_connection(connection_id, auth_token=auth_token, entity_types=payload.entity_types)
    if result.status == "error" or result.error is not None:
        # A sync that reports an error (inactive connection, no entity
        # mappings, no base URL, …) must surface as a failure, not a silent
        # 200 — otherwise the caller cannot distinguish "synced" from "did
        # nothing" and the platform data is silently never fetched.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Sync failed.",
        )
    return SyncResponseSchema(**result.to_dict())


@router.delete("/connections/{connection_id}", response_model=DeleteResponseSchema)
async def delete_connection(
    connection_id: str,
    store_id: str = Depends(get_current_store_id),
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> DeleteResponseSchema:
    existing = await service.get_connection(connection_id)
    if not _connection_is_owned(existing, store_id):
        raise IntegrationConnectionNotFoundException(connection_id)
    success = await service.delete_connection(connection_id)
    return DeleteResponseSchema(success=success)
