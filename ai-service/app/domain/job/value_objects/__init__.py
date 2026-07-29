from enum import Enum


class JobType(str, Enum):
    DOCUMENT_PROCESSING = "document_processing"
    CHUNK_GENERATION = "chunk_generation"
    SUMMARY_GENERATION = "summary_generation"
    EMBEDDING_GENERATION = "embedding_generation"
    VECTOR_SYNC = "vector_sync"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


__all__ = ["JobType", "JobStatus"]
