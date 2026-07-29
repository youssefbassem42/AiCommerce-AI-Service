from app.domain.knowledge.exceptions import KnowledgeDomainException


class JobNotFoundException(KnowledgeDomainException):
    pass


class JobAlreadyCompletedException(KnowledgeDomainException):
    pass


class JobMaxRetriesExceededException(KnowledgeDomainException):
    pass
