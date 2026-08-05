import logging

from fastapi import APIRouter, Depends, Query, status

from app.agents.integration.agent import IntegrationMappingAgent
from app.api.auth.dependencies import (
    get_current_store_id,
    get_optional_organization_id,
    require_admin_role,
)
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
    ConnectionResponseDTO,
    EntityMappingDTO,
    FieldMappingDTO,
    PaginationConfigDTO,
    ParseSpecRequestDTO,
)
from app.application.integration.mapping.services import IntegrationApplicationService
from app.application.integration.sync.orchestrator import SyncOrchestrator
from app.domain.integration.exceptions import IntegrationConnectionNotFoundException
from app.workflows.integration.graph import IntegrationWorkflow

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/integration",
    tags=["Integration"],
    dependencies=[Depends(require_admin_role)],
)


def _connection_is_owned(connection: ConnectionResponseDTO, store_id: str) -> bool:
    return bool(connection) and connection.store_id == store_id


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
    service: IntegrationApplicationService = Depends(get_integration_service),
    store_id: str = Depends(get_current_store_id),
    organization_id: str | None = Depends(get_optional_organization_id),
) -> ConnectionResponseSchema:
    dto = ConnectionCreateDTO(
        store_id=store_id,
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
    store_id: str = Depends(get_current_store_id),
    orchestrator: SyncOrchestrator = Depends(get_sync_orchestrator),
    service: IntegrationApplicationService = Depends(get_integration_service),
) -> SyncResponseSchema:
    existing = await service.get_connection(connection_id)
    if not _connection_is_owned(existing, store_id):
        raise IntegrationConnectionNotFoundException(connection_id)
    result = await orchestrator.sync_connection(connection_id)
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
