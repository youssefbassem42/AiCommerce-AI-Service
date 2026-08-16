import logging

from fastapi import APIRouter, Depends, Query, status

from app.api.auth.dependencies import get_current_store_id, require_admin_role
from app.api.knowledge.generation_dependencies import (
    get_generate_handler,
    get_list_history_handler,
    get_regenerate_handler,
)
from app.api.knowledge.generation_schemas import (
    BusinessSummaryGenerationResponseSchema,
    GenerateBusinessSummaryRequestSchema,
    PaginatedBusinessSummaryHistoryResponseSchema,
)
from app.application.knowledge.commands.generate_business_summary_command import (
    GenerateBusinessSummaryCommand,
    RegenerateBusinessSummaryCommand,
)
from app.application.knowledge.generation.config import GenerationConfig
from app.application.knowledge.queries.list_business_summary_history_query import (
    ListBusinessSummaryHistoryQuery,
)
from app.core.ai_settings import ai_settings
from app.core.knowledge_settings import knowledge_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=knowledge_settings.route_prefix,
    tags=["Knowledge Base"],
    dependencies=[Depends(require_admin_role)],
)


def _to_response(entity) -> BusinessSummaryGenerationResponseSchema:
    metadata = entity.metadata or {}
    sections = metadata.get("sections", {})
    return BusinessSummaryGenerationResponseSchema(
        id=entity.id,
        document_id=entity.document_id,
        version_number=entity.version_number,
        title=entity.title,
        summary=entity.summary,
        metadata=metadata,
        sections=sections,
        document_count=metadata.get("document_count", 0),
        model=metadata.get("model"),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.post(
    "/summaries/generate",
    response_model=BusinessSummaryGenerationResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def generate_business_summary(
    payload: GenerateBusinessSummaryRequestSchema = Depends(lambda: GenerateBusinessSummaryRequestSchema()),
    store_id: str = Depends(get_current_store_id),
    handler: "GenerateBusinessSummaryHandler" = Depends(get_generate_handler),
):
    cfg = None
    if payload.model or payload.temperature is not None or payload.max_tokens is not None:
        cfg = GenerationConfig(
            model=payload.model or ai_settings.DEFAULT_MODEL,
            temperature=payload.temperature if payload.temperature is not None else 0.3,
            max_tokens=payload.max_tokens or 4096,
        )
    command = GenerateBusinessSummaryCommand(store_id=store_id, config=cfg)
    result = await handler.handle(command)
    return _to_response(result)


@router.post(
    "/summaries/regenerate",
    response_model=BusinessSummaryGenerationResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def regenerate_business_summary(
    payload: GenerateBusinessSummaryRequestSchema = Depends(lambda: GenerateBusinessSummaryRequestSchema()),
    store_id: str = Depends(get_current_store_id),
    handler: "RegenerateBusinessSummaryHandler" = Depends(get_regenerate_handler),
):
    cfg = None
    if payload.model or payload.temperature is not None or payload.max_tokens is not None:
        cfg = GenerationConfig(
            model=payload.model or ai_settings.DEFAULT_MODEL,
            temperature=payload.temperature if payload.temperature is not None else 0.3,
            max_tokens=payload.max_tokens or 4096,
        )
    command = RegenerateBusinessSummaryCommand(store_id=store_id, config=cfg)
    result = await handler.handle(command)
    return _to_response(result)


@router.get(
    "/summaries/history",
    response_model=PaginatedBusinessSummaryHistoryResponseSchema,
)
async def list_business_summary_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=knowledge_settings.default_page_size, ge=1, le=knowledge_settings.max_page_size),
    store_id: str = Depends(get_current_store_id),
    handler: "ListBusinessSummaryHistoryHandler" = Depends(get_list_history_handler),
):
    query = ListBusinessSummaryHistoryQuery(store_id=store_id, page=page, page_size=page_size)
    result = await handler.handle(query)
    items = [
        BusinessSummaryGenerationResponseSchema(
            id=item.id,
            document_id=item.document_id,
            version_number=item.version_number,
            title=item.title,
            summary=item.summary,
            metadata=item.metadata,
            sections=item.metadata.get("sections", {}),
            document_count=item.metadata.get("document_count", 0),
            model=item.metadata.get("model"),
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in result.items
    ]
    return PaginatedBusinessSummaryHistoryResponseSchema(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
