import logging
import os
import tempfile

from fastapi import Depends, UploadFile

from app.application.knowledge.services import (
    BusinessSummaryService,
    DocumentUploadService,
    KnowledgeChunkService,
    KnowledgeDocumentService,
)
from app.core.knowledge_settings import knowledge_settings
from app.infrastructure.mongodb.repositories.business_summary_repository import (
    BusinessSummaryRepository,
)
from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository
from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository
from app.infrastructure.mongodb.repositories.upload_repository import UploadRepository
from app.infrastructure.storage.local_provider import LocalStorageProvider
from app.infrastructure.storage.provider import StorageProvider

logger = logging.getLogger(__name__)


def get_knowledge_repository() -> KnowledgeRepository:
    return KnowledgeRepository()


def get_chunk_repository() -> ChunkRepository:
    return ChunkRepository()


def get_business_summary_repository() -> BusinessSummaryRepository:
    return BusinessSummaryRepository()


def get_upload_repository() -> UploadRepository:
    return UploadRepository()


def get_storage_provider() -> StorageProvider:
    backend = knowledge_settings.upload_storage_backend
    if backend == "local":
        return LocalStorageProvider(upload_dir=knowledge_settings.upload_local_path)
    logger.warning("Unknown storage backend '%s', falling back to local", backend)
    return LocalStorageProvider(upload_dir=knowledge_settings.upload_local_path)


def get_knowledge_document_service(
    repository: KnowledgeRepository = Depends(get_knowledge_repository),
) -> KnowledgeDocumentService:
    return KnowledgeDocumentService(repository=repository)


def get_knowledge_chunk_service(
    repository: ChunkRepository = Depends(get_chunk_repository),
) -> KnowledgeChunkService:
    return KnowledgeChunkService(repository=repository)


def get_business_summary_service(
    repository: BusinessSummaryRepository = Depends(get_business_summary_repository),
) -> BusinessSummaryService:
    return BusinessSummaryService(repository=repository)


def get_document_upload_service(
    repository: UploadRepository = Depends(get_upload_repository),
    storage: StorageProvider = Depends(get_storage_provider),
) -> DocumentUploadService:
    return DocumentUploadService(repository=repository, storage=storage)


async def write_upload_temp(file: UploadFile) -> str:
    """Write an uploaded file to a temporary location and return the path."""
    suffix = os.path.splitext(file.filename or "upload")[1]
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as dest:
            content = await file.read()
            dest.write(content)
    except Exception:
        os.unlink(temp_path)
        raise
    return temp_path
