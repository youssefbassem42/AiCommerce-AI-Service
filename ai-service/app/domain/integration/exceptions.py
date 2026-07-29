from app.core.exceptions import DomainException


class IntegrationDomainException(DomainException):
    """Base exception for integration domain failures."""


class IntegrationValidationException(IntegrationDomainException):
    """Raised when an integration domain object violates business rules."""


class IntegrationConnectionNotFoundException(IntegrationDomainException):
    """Raised when an integration connection cannot be found."""

    def __init__(self, connection_id: str):
        super().__init__(f"Integration connection '{connection_id}' was not found.")


class InvalidSpecException(IntegrationValidationException):
    """Raised when a spec is missing required structure or cannot be parsed."""


class InvalidMappingException(IntegrationValidationException):
    """Raised when a field/entity mapping is invalid."""


class DuplicateConnectionException(IntegrationValidationException):
    """Raised when a connection with the same name already exists in the store."""
