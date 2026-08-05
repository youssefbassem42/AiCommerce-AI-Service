from app.core.exceptions import DomainException


class KnowledgeDomainException(DomainException):
    """Base exception for knowledge domain failures."""


class KnowledgeValidationException(KnowledgeDomainException):
    """Raised when a knowledge domain object violates business rules."""


class KnowledgeDocumentNotFoundException(KnowledgeDomainException):
    """Raised when a knowledge document cannot be found."""

    status_code = 404


class KnowledgeChunkNotFoundException(KnowledgeDomainException):
    """Raised when a knowledge chunk cannot be found."""

    status_code = 404


class BusinessSummaryNotFoundException(KnowledgeDomainException):
    """Raised when a business summary cannot be found."""

    status_code = 404


class UploadNotFoundException(KnowledgeDomainException):
    """Raised when a document upload record cannot be found."""

    status_code = 404


class DuplicateUploadException(KnowledgeDomainException):
    """Raised when a duplicate file upload is detected."""

    status_code = 409


class FileValidationException(KnowledgeDomainException):
    """Raised when a file fails validation checks."""

    status_code = 409


class ChunkingException(KnowledgeDomainException):
    """Raised when document chunking fails."""
