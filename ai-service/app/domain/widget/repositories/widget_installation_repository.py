"""Widget installation repository interface and domain errors.

Authentication errors intentionally carry generic messages: a failed bootstrap
must not leak tenant or installation information to the untrusted browser widget.
"""

from app.core.exceptions import DomainException
from app.domain.widget.entities.widget_installation import WidgetInstallation
from app.shared.kernel.repository import AsyncRepository


class WidgetInstallationNotFoundError(DomainException):
    """Raised when no installation matches the presented key, or when the
    installation exists but is not active (both surface as generic 401s so the
    browser cannot distinguish them)."""

    status_code = 401

    def __init__(self) -> None:
        super().__init__("Invalid widget key")


class WidgetOriginNotAllowedError(DomainException):
    """Raised when the request Origin is not in the installation's allowed origins."""

    status_code = 403

    def __init__(self) -> None:
        super().__init__("Origin not allowed for this widget installation")


class WidgetConfigurationError(DomainException):
    """Raised when widget installation configuration is invalid (e.g. bad origins)."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class WidgetInstallationLimitError(DomainException):
    """Raised when a store exceeds the maximum number of widget installations."""

    status_code = 409

    def __init__(self) -> None:
        super().__init__("Widget installation limit reached for this store")


class WidgetInstallationRepository(AsyncRepository[WidgetInstallation, str]):
    async def find_by_public_key_hash(self, public_key_hash: str) -> WidgetInstallation | None:
        """Find an installation by the SHA-256 hash of its public widget key."""
        raise NotImplementedError

    async def find_by_widget_id(self, widget_id: str) -> WidgetInstallation | None:
        """Find an installation by its public widget identifier."""
        raise NotImplementedError

    async def find_by_store_id(self, store_id: str) -> list[WidgetInstallation]:
        """List installations for a store."""
        raise NotImplementedError

    async def touch_last_used(self, installation_id: str) -> None:
        """Bump `last_used_at` after a successful bootstrap."""
        raise NotImplementedError

    async def find_allowed_origins(self) -> set[str]:
        """All origins allow-listed by active installations (for dynamic CORS)."""
        raise NotImplementedError
