from app.core.exceptions import DomainException


class CommerceDomainException(DomainException):
    """Base exception for commerce domain failures."""


class CommerceValidationException(CommerceDomainException):
    """Raised when a commerce domain object violates business rules."""


class ProductNotFoundException(CommerceDomainException):
    """Raised when a product cannot be found."""


class CategoryNotFoundException(CommerceDomainException):
    """Raised when a category cannot be found."""


class OrderNotFoundException(CommerceDomainException):
    """Raised when an order cannot be found."""


class InventoryNotFoundException(CommerceDomainException):
    """Raised when an inventory record cannot be found."""
