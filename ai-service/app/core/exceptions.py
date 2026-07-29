class DomainException(Exception):
    """Base exception for all domain-related errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class EntityNotFoundException(DomainException):
    """Raised when a requested entity cannot be found."""
    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(f"Entity '{entity_name}' with ID '{entity_id}' was not found.")

class InfrastructureException(Exception):
    """Base exception for all infrastructure-related errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class DatabaseValidationException(InfrastructureException):
    """Raised when MongoDB schema validation fails on write."""
    def __init__(self, message: str):
        super().__init__(message)

class ConcurrencyException(InfrastructureException):
    """Raised when a concurrent write collision is detected."""
    def __init__(self, message: str):
        super().__init__(message)
