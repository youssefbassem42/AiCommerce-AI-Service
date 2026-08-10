"""Widget bootstrap flow.

The browser widget presents its opaque widget key; bootstrap resolves the
installation (cached), validates base state (exists + active, origin allow-listed)
and mints a short-lived scoped session token.

Security posture:
- The widget key is never persisted in readable form (installation stores only the
  SHA-256 hash); the browser sends the raw key bytes over the wire header.
- All bootstrap failures surface as a single generic 401/403 — an attacker cannot
  distinguish "bad key" from "disabled installation" from "unknown tenant".
- Origin is validated against the installation's allow-list; a wildcard origin is
  never permitted.
"""

import hashlib
import logging
from dataclasses import dataclass

from app.application.widget.cached_origin_service import CachedWidgetOriginService
from app.application.widget.token_service import WidgetTokenService
from app.domain.widget.entities.widget_installation import WidgetInstallation
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetInstallationNotFoundError,
    WidgetOriginNotAllowedError,
)
from app.infrastructure.mongodb.repositories.widget_installation_repository import (
    WidgetInstallationMongoRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WidgetBootstrapSession:
    access_token: str
    expires_in: int
    widget_id: str
    configuration: dict


class WidgetBootstrapService:
    def __init__(
        self,
        repository: WidgetInstallationMongoRepository,
        token_service: WidgetTokenService,
        origin_cache: CachedWidgetOriginService | None = None,
    ):
        self._repository = repository
        self._token_service = token_service
        self._origin_cache = origin_cache or CachedWidgetOriginService(repository)

    async def bootstrap(self, widget_key: str, origin: str | None) -> WidgetBootstrapSession:
        installation = await self._resolve_installation(widget_key)
        self._assert_origin_allowed(installation, origin)

        token, expires_in = self._token_service.create_session_token(
            widget_id=installation.widget_id,
            store_id=installation.store_id,
            organization_id=installation.organization_id,
            scopes=installation.scopes,
        )
        await self._repository.touch_last_used(installation.id)

        return WidgetBootstrapSession(
            access_token=token,
            expires_in=expires_in,
            widget_id=installation.widget_id,
            configuration={
                "chat": "rag:chat" in installation.scopes,
                "recommendations": "recommendations:read" in installation.scopes,
            },
        )

    async def _resolve_installation(self, widget_key: str) -> WidgetInstallation:
        public_key_hash = hashlib.sha256(widget_key.encode("utf-8")).hexdigest()
        try:
            installation = await self._origin_cache.resolve(public_key_hash)
        except Exception:
            logger.warning("Origin cache resolution failed; falling back to repository", exc_info=True)
            installation = await self._repository.find_by_public_key_hash(public_key_hash)
        if installation is None or not installation.is_active:
            raise WidgetInstallationNotFoundError()
        return installation

    @staticmethod
    def _assert_origin_allowed(installation: WidgetInstallation, origin: str | None) -> None:
        if origin:
            normalized = origin.rstrip("/")
            if normalized in installation.allowed_origins:
                return
            raise WidgetOriginNotAllowedError()
        if not installation.allowed_origins:
            return
        raise WidgetOriginNotAllowedError()
