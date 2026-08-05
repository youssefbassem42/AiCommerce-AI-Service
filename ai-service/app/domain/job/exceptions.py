from app.domain.knowledge.exceptions import KnowledgeDomainException


class JobNotFoundException(KnowledgeDomainException):
    """Raised when a job cannot be found."""

    status_code = 404


class JobAlreadyCompletedException(KnowledgeDomainException):
    """Raised when an already completed job is mutated."""

    status_code = 409


class JobMaxRetriesExceededException(KnowledgeDomainException):
    """Raised when a job exceeds its retry budget."""

    status_code = 409
