"""Widget installation provisioning (admin flow).

Creates a widget installation binding an opaque widget key to a tenant. Flow:
- Validate the provisioning payload (origins syntax/count, environment).
- Enforce the per-store installation limit.
- Generate an opaque `wi_...` widget key; only its SHA-256 hash is ever persisted.
- Persist the installation and hand the key back ONCE (it cannot be retrieved
  later — the hash is one-way).
"""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from app.domain.widget.entities.widget_installation import (
    WIDGET_DEFAULT_SCOPES,
    WIDGET_STATUS_ACTIVE,
    WIDGET_STATUS_DISABLED,
    WidgetInstallation,
)
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetConfigurationError,
    WidgetInstallationLimitError,
    WidgetInstallationNotFoundError,
    WidgetInstallationRepository,
)

logger = logging.getLogger(__name__)

WIDGET_KEY_PREFIX = "wi_"
WIDGET_ID_PREFIX = "wid_"
MAX_ALLOWED_ORIGINS = 5
MAX_INSTALLATIONS_PER_STORE = 5
MAX_KEY_GENERATION_ATTEMPTS = 5


def normalize_origin(origin: str) -> str:
    """Normalize a merchant origin (scheme + host, no path/query/fragment).

    Raises WidgetConfigurationError for anything that is not a bare
    `https://host[:port]` (or http) origin.
    """
    value = origin.strip()
    if not value or value.endswith("/"):
        value = value.rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path not in ("", "/"):
        raise WidgetConfigurationError(f"Invalid origin: '{origin}'. Use a bare origin like https://store.example.com")
    host = parsed.hostname or ""
    if not host or "." not in host and host != "localhost":
        raise WidgetConfigurationError(f"Invalid origin host: '{origin}'")
    port = parsed.port
    normalized = f"{parsed.scheme}://{host}"
    if port is not None:
        normalized = f"{normalized}:{port}"
    return normalized


class WidgetInstallationService:
    def __init__(self, repository: WidgetInstallationRepository):
        self.repository = repository
        self._on_created = None  # hook for cache invalidation (set by wiring)

    def set_on_created(self, callback) -> None:
        self._on_created = callback

    async def create(
        self,
        store_id: str,
        organization_id: str,
        environment: str = "live",
        allowed_origins: list[str] | None = None,
        scopes: list[str] | None = None,
    ) -> tuple[WidgetInstallation, str]:
        """Create a widget installation and return (installation, widget_key).

        The widget key is returned once and cannot be recovered later.
        """
        if environment not in ("live", "test"):
            raise WidgetConfigurationError("environment must be 'live' or 'test'")

        origins = [normalize_origin(o) for o in (allowed_origins or [])]
        if len(origins) > MAX_ALLOWED_ORIGINS:
            raise WidgetConfigurationError(
                f"At most {MAX_ALLOWED_ORIGINS} allowed origins are permitted"
            )

        requested_scopes = [s for s in (scopes or list(WIDGET_DEFAULT_SCOPES)) if s]
        valid_scopes = {"rag:chat", "recommendations:read"}
        unknown = set(requested_scopes) - valid_scopes
        if unknown:
            raise WidgetConfigurationError(
                f"Unknown widget scopes: {', '.join(sorted(unknown))}"
            )

        existing = await self.repository.find_by_store_id(store_id)
        active = [i for i in existing if i.status == WIDGET_STATUS_ACTIVE]
        if len(active) >= MAX_INSTALLATIONS_PER_STORE:
            raise WidgetInstallationLimitError()

        widget_key, public_key_hash = await self._generate_unique_key()
        installation = WidgetInstallation(
            id=f"inst_{uuid.uuid4().hex}",
            widget_id=f"{WIDGET_ID_PREFIX}{uuid.uuid4().hex[:16]}",
            store_id=store_id,
            organization_id=organization_id,
            public_key_hash=public_key_hash,
            environment=environment,
            status=WIDGET_STATUS_ACTIVE,
            allowed_origins=origins,
            scopes=requested_scopes,
            last_used_at=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created = await self.repository.create(installation)
        logger.info(
            "Provisioned widget installation %s for store %s (%s origins)",
            created.widget_id,
            store_id,
            len(origins),
        )
        if self._on_created:
            self._on_created()

        return created, widget_key

    async def list_for_store(self, store_id: str) -> list[WidgetInstallation]:
        """List the store's widget installations (widget keys are never stored)."""
        return await self.repository.find_by_store_id(store_id)

    async def disable(self, widget_id: str, store_id: str) -> WidgetInstallation:
        """Disable an installation belonging to the store; bootstrap/scope denials follow.

        Returns the updated installation (404 when unknown or owned by another store).
        """
        installation = await self.repository.find_by_widget_id(widget_id)
        if installation is None or installation.store_id != store_id:
            raise WidgetInstallationNotFoundError()
        installation.status = WIDGET_STATUS_DISABLED
        installation.updated_at = datetime.now(UTC)
        updated = await self.repository.update(installation)
        logger.info("Disabled widget installation %s for store %s", updated.widget_id, store_id)
        if self._on_created:
            self._on_created()
        return updated

    async def _generate_unique_key(self) -> tuple[str, str]:
        for _ in range(MAX_KEY_GENERATION_ATTEMPTS):
            widget_key = f"{WIDGET_KEY_PREFIX}{secrets.token_urlsafe(32)}"
            public_key_hash = hashlib.sha256(widget_key.encode("utf-8")).hexdigest()
            existing = await self.repository.find_by_public_key_hash(public_key_hash)
            if existing is None:
                return widget_key, public_key_hash
        raise WidgetConfigurationError("Could not generate a unique widget key; retry")
