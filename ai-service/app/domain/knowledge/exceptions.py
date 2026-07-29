class KnowledgeDomainException(Exception):
    """Base exception for knowledge domain failures."""


class KnowledgeValidationException(KnowledgeDomainException):
    """Raised when a knowledge domain object violates business rules."""


class KnowledgeDocumentNotFoundException(KnowledgeDomainException):
    """Raised when a knowledge document cannot be found."""


class KnowledgeChunkNotFoundException(KnowledgeDomainException):
    """Raised when a knowledge chunk cannot be found."""


class BusinessSummaryNotFoundException(KnowledgeDomainException):
    """Raised when a business summary cannot be found."""


class UploadNotFoundException(KnowledgeDomainException):
    """Raised when a document upload record cannot be found."""


class DuplicateUploadException(KnowledgeDomainException):
    """Raised when a duplicate file upload is detected."""


class FileValidationException(KnowledgeDomainException):
    """Raised when a file fails validation checks."""


class ChunkingException(KnowledgeDomainException):
    """Raised when document chunking fails."""
