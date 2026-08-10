"""TTL-cached widget origin resolution.

Bootstrap looks the widget key up on every call; caching the resolved installation
per key hash removes the hotspot while a short TTL bounds staleness (a disabled or
edited installation is enforced within the TTL, and `clear()` invalidates the cache
immediately after provisioning).
"""

import logging
import time
from dataclasses import dataclass

from app.domain.widget.entities.widget_installation import WidgetInstallation
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetInstallationRepository,
)

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class _CacheEntry:
    expires_at: float
    installation: WidgetInstallation | None


class CachedWidgetOriginService:
    """Resolves installations by public key hash with a short-TTL in-process cache."""

    def __init__(self, repository: WidgetInstallationRepository, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        self._repository = repository
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, _CacheEntry] = {}

    async def resolve(self, public_key_hash: str) -> WidgetInstallation | None:
        now = time.monotonic()
        entry = self._cache.get(public_key_hash)
        if entry is not None and entry.expires_at > now:
            return entry.installation

        installation = await self._repository.find_by_public_key_hash(public_key_hash)
        self._cache[public_key_hash] = _CacheEntry(
            expires_at=now + self._ttl_seconds,
            installation=installation,
        )
        return installation

    def clear(self) -> None:
        """Invalidate the whole cache (called after provisioning changes)."""
        self._cache.clear()
