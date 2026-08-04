from app.core.exceptions import DomainException


class CommerceDomainException(DomainException):
    """Base exception for commerce domain failures."""


class CommerceValidationException(CommerceDomainException):
    """Raised when a commerce domain object violates business rules."""


class ProductNotFoundException(CommerceDomainException):
    """Raised when a product cannot be found."""

    status_code = 404


class CategoryNotFoundException(CommerceDomainException):
    """Raised when a category cannot be found."""

    status_code = 404


class OrderNotFoundException(CommerceDomainException):
    """Raised when an order cannot be found."""

    status_code = 404


class InventoryNotFoundException(CommerceDomainException):
    """Raised when an inventory record cannot be found."""

    status_code = 404
