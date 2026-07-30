import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.agents.integration.agent import IntegrationMappingAgent
from app.api.analytics.dependencies import require_admin_role
from app.api.integration.dependencies import (
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
from app.application.integration.mapping.dto import (
    AuthConfigDTO,
    ConnectionCreateDTO,
    EntityMappingDTO,
    FieldMappingDTO,
    PaginationConfigDTO,
    ParseSpecRequestDTO,
)
from app.application.integration.mapping.services import IntegrationApplicationService
from app.application.integration.sync.orchestrator import SyncOrchestrator
from app.domain.integration.exceptions import (
    DuplicateConnectionException,
    IntegrationConnectionNotFoundException,
    IntegrationDomainException,
    IntegrationValidationException,
    InvalidMappingException,
    InvalidSpecException,
)
from app.workflows.integration.graph import IntegrationWorkflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integration", tags=["Integration"])


def _handle_exception(exc: Exception) -> None:
    if isinstance(exc, IntegrationConnectionNotFoundException):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (IntegrationValidationException, InvalidMappingException, InvalidSpecException)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, DuplicateConnectionException):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, IntegrationDomainException):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.exception("Unhandled integration error")
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/schemas/parse", response_model=ParseSpecResponseSchema, status_code=status.HTTP_200_OK)
async def parse_spec(
    payload: ParseSpecRequestSchema,
    request: Request,
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> ParseSpecResponseSchema:
    try:
        dto = ParseSpecRequestDTO(
            platform_name=payload.platform_name,
            raw_spec=payload.raw_spec,
        )
        result = await service.parse_spec(dto)
        return ParseSpecResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.post("/schemas/agent-parse", response_model=AgentParseResponseSchema, status_code=status.HTTP_200_OK)
async def agent_parse_spec(
    payload: AgentParseRequestSchema,
    request: Request,
    agent: IntegrationMappingAgent = Depends(get_integration_agent),
) -> AgentParseResponseSchema:
    try:
        store_id = getattr(request.state, "store_id", "default")
        org_id = getattr(request.state, "tenant_id", "default")

        report, error, capabilities = await agent.analyze(
            raw_spec=payload.raw_spec,
            platform_name=payload.platform_name,
            store_id=store_id,
            organization_id=org_id,
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
    except Exception as exc:
        _handle_exception(exc)


@router.post("/agent-sync", response_model=AgentSyncResponseSchema, status_code=status.HTTP_200_OK)
async def agent_sync(
    payload: AgentSyncRequestSchema,
    request: Request,
    workflow: IntegrationWorkflow = Depends(get_integration_workflow),
) -> AgentSyncResponseSchema:
    try:
        organization_id = getattr(request.state, "tenant_id", payload.store_id)

        result = await workflow.run(
            raw_spec=payload.raw_spec,
            platform_name=payload.platform_name,
            store_id=payload.store_id,
            organization_id=organization_id,
            credentials=payload.credentials,
            connection_name=payload.name,
            auto_sync=payload.auto_sync,
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
    except Exception as exc:
        _handle_exception(exc)


@router.post("/connections", response_model=ConnectionResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_connection(
    payload: CreateConnectionSchema,
    request: Request,
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> ConnectionResponseSchema:
    try:
        organization_id = getattr(request.state, "tenant_id", payload.store_id)
        dto = ConnectionCreateDTO(
            store_id=payload.store_id,
            organization_id=organization_id,
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
        result = await service.create_connection(dto)
        return ConnectionResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/connections", response_model=PaginatedConnectionResponseSchema)
async def list_connections(
    request: Request,
    store_id: str = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> PaginatedConnectionResponseSchema:
    try:
        items, total = await service.list_connections(store_id=store_id, page=page, page_size=page_size)
        return PaginatedConnectionResponseSchema(
            items=[ConnectionResponseSchema(**item.model_dump()) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        _handle_exception(exc)


@router.get("/connections/{connection_id}", response_model=ConnectionResponseSchema)
async def get_connection(
    connection_id: str,
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> ConnectionResponseSchema:
    try:
        result = await service.get_connection(connection_id)
        return ConnectionResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.put("/connections/{connection_id}/mappings", response_model=ConnectionResponseSchema)
async def update_connection_mappings(
    connection_id: str,
    payload: UpdateMappingsSchema,
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> ConnectionResponseSchema:
    try:
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
    except Exception as exc:
        _handle_exception(exc)


@router.put("/connections/{connection_id}/credentials", response_model=ConnectionResponseSchema)
async def update_connection_credentials(
    connection_id: str,
    payload: UpdateCredentialsSchema,
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> ConnectionResponseSchema:
    try:
        result = await service.update_credentials(
            connection_id=connection_id,
            auth_config_dto=AuthConfigDTO(**payload.auth_config.model_dump()),
            credentials=payload.credentials,
        )
        return ConnectionResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.post(
    "/connections/{connection_id}/sync",
    response_model=SyncResponseSchema,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_role)],
)
async def sync_connection(
    connection_id: str,
    payload: SyncRequestSchema,
    orchestrator: SyncOrchestrator = Depends(get_sync_orchestrator),
) -> SyncResponseSchema:
    try:
        result = await orchestrator.sync_connection(connection_id)
        return SyncResponseSchema(**result.to_dict())
    except Exception as exc:
        _handle_exception(exc)


@router.delete("/connections/{connection_id}", response_model=DeleteResponseSchema)
async def delete_connection(
    connection_id: str,
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> DeleteResponseSchema:
    try:
        success = await service.delete_connection(connection_id)
        return DeleteResponseSchema(success=success)
    except Exception as exc:
        _handle_exception(exc)
