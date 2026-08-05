from app.core.exceptions import DomainException


class AuthDomainException(DomainException):
    """Base exception for auth domain failures."""


class AuditLogNotFoundException(AuthDomainException):
    """Raised when an audit log entry cannot be found."""

    status_code = 404
