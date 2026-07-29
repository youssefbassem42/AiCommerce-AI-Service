import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth.dependencies import get_api_key_repository, get_audit_log_repository
from app.api.auth.schemas import (
    ApiKeyCreateRequest,
    ApiKeyListResponse,
    ApiKeyResponse,
    AuditLogResponse,
)
from app.domain.auth.entities.api_key import ApiKey
from app.infrastructure.mongodb.repositories.api_key_repository import ApiKeyRepository
from app.infrastructure.mongodb.repositories.audit_log_repository import AuditLogRepository

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.get("/api-keys/{store_id}", response_model=ApiKeyListResponse)
async def list_api_keys(
    store_id: str,
    repo: ApiKeyRepository = Depends(get_api_key_repository),
) -> ApiKeyListResponse:
    keys = await repo.find_by_store_id(store_id)
    return ApiKeyListResponse(
        api_keys=[
            ApiKeyResponse(
                key_prefix=k.key_prefix,
                name=k.name,
                scopes=k.scopes,
                is_active=k.is_active,
                expires_at=k.expires_at,
                created_at=k.created_at,
            )
            for k in keys
        ]
    )


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
    request: ApiKeyCreateRequest,
    repo: ApiKeyRepository = Depends(get_api_key_repository),
) -> ApiKeyResponse:
    raw_key = f"ak_{secrets.token_urlsafe(32)}"
    key_hash = ApiKeyRepository.hash_key(raw_key)
    key_prefix = ApiKeyRepository.generate_key_prefix(raw_key)

    entity = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=request.name,
        store_id=request.store_id,
        scopes=request.scopes,
        expires_at=request.expires_at,
    )
    created = await repo.create(entity)

    return ApiKeyResponse(
        key_prefix=created.key_prefix,
        name=created.name,
        scopes=created.scopes,
        is_active=created.is_active,
        expires_at=created.expires_at,
        created_at=created.created_at,
    )


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    repo: ApiKeyRepository = Depends(get_api_key_repository),
) -> None:
    key = await repo.find_by_id(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    await repo.update(key)


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    skip: int = 0,
    limit: int = 50,
    repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> List[AuditLogResponse]:
    logs = await repo.find_many({}, limit=limit, skip=skip)
    return [
        AuditLogResponse(
            id=log.id,
            tenant_id=log.tenant_id or "",
            user_id=log.actor_id or "",
            action=log.action,
            resource=log.resource_type,
            outcome=log.outcome,
            timestamp=log.timestamp,
        )
        for log in logs
    ]
