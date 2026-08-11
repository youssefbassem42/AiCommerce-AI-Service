from app.core.exceptions import DomainException


class IntegrationDomainException(DomainException):
    """Base exception for integration domain failures."""


class IntegrationValidationException(IntegrationDomainException):
    """Raised when an integration domain object violates business rules."""


class IntegrationConnectionNotFoundException(IntegrationDomainException):
    """Raised when an integration connection cannot be found."""

    status_code = 404

    def __init__(self, connection_id: str):
        super().__init__(f"Integration connection '{connection_id}' was not found.")


class InvalidSpecException(IntegrationValidationException):
    """Raised when a spec is missing required structure or cannot be parsed."""


class IntegrationApiException(IntegrationDomainException):
    """Raised when an external API returns an unusable response (HTTP error or non-JSON body)."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class IntegrationAuthenticationError(IntegrationDomainException):
    """Raised when e-commerce authentication fails.

    Surfaced as HTTP 401 so the caller can validate the e-commerce admin panel
    email/password. Guarantees no connection is created and no data is synced.
    ``details`` may carry a fallback sync summary (public data fetched/stored,
    admin-protected endpoints skipped).
    """

    status_code = 401

    def __init__(self, message: str | None = None, details: dict | None = None):
        self.details = details
        super().__init__(
            message
            or "E-commerce authentication failed. Check the e-commerce admin panel email and password."
        )


class InvalidMappingException(IntegrationValidationException):
    """Raised when a field/entity mapping is invalid."""


class DuplicateConnectionException(IntegrationValidationException):
    """Raised when a connection with the same name already exists in the store."""

    status_code = 409
