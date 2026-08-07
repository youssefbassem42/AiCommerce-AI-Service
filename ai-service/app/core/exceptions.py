class DomainException(Exception):
    """Base exception for all domain-related errors.

    ``status_code`` drives the HTTP status returned by the global exception
    handlers; subclasses override it to express their semantics.
    """

    status_code: int = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class EntityNotFoundException(DomainException):
    """Raised when a requested entity cannot be found."""

    status_code = 404

    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(f"Entity '{entity_name}' with ID '{entity_id}' was not found.")


class InfrastructureException(Exception):
    """Base exception for all infrastructure-related errors."""

    status_code: int = 503

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class DatabaseValidationException(InfrastructureException):
    """Raised when MongoDB schema validation fails on write."""

    status_code = 422

    def __init__(self, message: str):
        super().__init__(message)


class ConcurrencyException(InfrastructureException):
    """Raised when a concurrent write collision is detected."""

    status_code = 409

    def __init__(self, message: str):
        super().__init__(message)


class TaskQueueUnavailableException(InfrastructureException):
    """Raised when an async job cannot be enqueued (e.g. broker is down).

    Keeps request handlers from leaking opaque 500s: callers can surface a
    clear, actionable message instead of an internal server error.
    """

    status_code = 503

    def __init__(self, message: str):
        super().__init__(message)
