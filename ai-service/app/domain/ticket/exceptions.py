from app.core.exceptions import DomainException


class TicketDomainException(DomainException):
    """Base exception for ticket domain failures."""


class TicketNotFoundException(TicketDomainException):
    """Raised when a ticket cannot be found."""

    status_code = 404
