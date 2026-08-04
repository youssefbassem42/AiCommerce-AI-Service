import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.admin.dependencies import get_prompt_service
from app.api.admin.schemas import (
    PromptCreateRequest,
    PromptListResponse,
    PromptResponse,
    PromptUpdateRequest,
)
from app.api.auth.dependencies import require_super_admin_role
from app.application.admin.services.prompt_service import PromptService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/prompts",
    tags=["Admin Prompts"],
    dependencies=[Depends(require_super_admin_role)],
)


def _to_response(prompt) -> PromptResponse:
    return PromptResponse(
        id=prompt.id,
        key=prompt.key,
        type=prompt.type,
        content=prompt.content,
        description=prompt.description,
        tags=prompt.tags,
        version=prompt.version,
        is_active=prompt.is_active,
        variables=prompt.variables,
        created_at=prompt.created_at.isoformat() if hasattr(prompt.created_at, "isoformat") else str(prompt.created_at),
        updated_at=prompt.updated_at.isoformat() if hasattr(prompt.updated_at, "isoformat") else str(prompt.updated_at),
    )


@router.get("", response_model=PromptListResponse)
async def list_prompts(
    query: str = Query("", description="Search in key, content, and description"),
    type: str | None = Query(None, alias="type", description="Filter by prompt type"),
    tags: str | None = Query(None, description="Comma-separated tag filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: PromptService = Depends(get_prompt_service),
):
    tag_list = tags.split(",") if tags else None
    items, total = await service.list_prompts(
        query=query,
        type_filter=type,
        tag_filter=tag_list,
        page=page,
        page_size=page_size,
    )
    return PromptListResponse(
        items=[_to_response(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{key}", response_model=PromptResponse)
async def get_prompt(
    key: str,
    service: PromptService = Depends(get_prompt_service),
):
    prompt = await service.get_prompt(key)
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt '{key}' not found")
    return _to_response(prompt)


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    payload: PromptCreateRequest,
    service: PromptService = Depends(get_prompt_service),
):
    try:
        prompt = await service.create_prompt(
            key=payload.key,
            type=payload.type,
            content=payload.content,
            description=payload.description,
            tags=payload.tags,
            variables=payload.variables,
        )
        return _to_response(prompt)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/{key}", response_model=PromptResponse)
async def update_prompt(
    key: str,
    payload: PromptUpdateRequest,
    service: PromptService = Depends(get_prompt_service),
):
    try:
        prompt = await service.update_prompt(
            key=key,
            content=payload.content,
            description=payload.description,
            tags=payload.tags,
            type=payload.type,
            variables=payload.variables,
            is_active=payload.is_active,
        )
        return _to_response(prompt)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    key: str,
    service: PromptService = Depends(get_prompt_service),
):
    deleted = await service.delete_prompt(key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt '{key}' not found")


@router.post("/{key}/restore", response_model=PromptResponse)
async def restore_prompt(
    key: str,
    service: PromptService = Depends(get_prompt_service),
):
    prompt = await service.restore_default(key)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No default prompt definition for '{key}'",
        )
    return _to_response(prompt)


@router.post("/seed", response_model=dict)
async def seed_prompts(
    service: PromptService = Depends(get_prompt_service),
):
    count = await service.seed_defaults()
    return {"seeded": count}
