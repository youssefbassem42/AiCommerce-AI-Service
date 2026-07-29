class AuthDomainException(Exception):
    """Base exception for auth domain failures."""


class ApiKeyNotFoundException(AuthDomainException):
    """Raised when an API key cannot be found."""


class ApiKeyExpiredException(AuthDomainException):
    """Raised when an API key has expired."""


class ApiKeyInactiveException(AuthDomainException):
    """Raised when an API key is inactive/revoked."""


class InvalidApiKeyException(AuthDomainException):
    """Raised when an API key is invalid."""


class AuditLogNotFoundException(AuthDomainException):
    """Raised when an audit log entry cannot be found."""
