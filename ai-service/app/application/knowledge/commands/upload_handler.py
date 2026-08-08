import hashlib
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime

from bson import ObjectId

from app.application.knowledge.commands.upload_command import UploadDocumentCommand
from app.application.knowledge.dto.upload_dto import UploadDTO
from app.core.exceptions import ConcurrencyException
from app.domain.knowledge.entities.document_upload import DocumentUpload
from app.domain.knowledge.exceptions import (
    FileValidationException,
)
from app.domain.knowledge.repositories.upload_repository import UploadRepository
from app.domain.knowledge.value_objects.document_metadata import DocumentMetadata
from app.infrastructure.storage.provider import StorageProvider

logger = logging.getLogger(__name__)

FileMirrorFn = Callable[[str, str], Awaitable[None]]

ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".txt", ".csv"}
ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "application/csv",
}
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024


def _new_id() -> str:
    return str(ObjectId())


def _compute_checksum(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _validate_extension(ext: str) -> None:
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise FileValidationException(f"Extension '{ext}' is not allowed. Allowed: {ALLOWED_EXTENSIONS}")


def _validate_mime_type(mime: str) -> None:
    if mime not in ALLOWED_MIME_TYPES:
        raise FileValidationException(f"MIME type '{mime}' is not allowed. Allowed: {ALLOWED_MIME_TYPES}")


def _validate_file_size(size: int) -> None:
    if size > MAX_FILE_SIZE_BYTES:
        raise FileValidationException(f"File size {size} bytes exceeds maximum of {MAX_FILE_SIZE_BYTES} bytes")


class UploadDocumentHandler:
    """Handles the UploadDocumentCommand — validates, stores, and persists upload metadata."""

    def __init__(
        self,
        repository: UploadRepository,
        storage: StorageProvider,
        file_mirror: FileMirrorFn | None = None,
    ):
        self.repository = repository
        self.storage = storage
        self.file_mirror = file_mirror

    async def handle(self, command: UploadDocumentCommand) -> UploadDTO:
        _validate_extension(os.path.splitext(command.original_filename)[1])
        _validate_mime_type(command.mime_type)
        _validate_file_size(command.file_size)

        checksum = _compute_checksum(command.file_path)

        existing = await self.repository.find_by_checksum(checksum, store_id=command.store_id)
        if existing is not None:
            with suppress(FileNotFoundError):
                os.remove(command.file_path)
            logger.info(
                "Duplicate upload within store; returning existing upload",
                extra={
                    "upload_id": existing.id,
                    "store_id": command.store_id,
                    "checksum": checksum[:16],
                },
            )
            return self._to_dto(existing).model_copy(update={"already_uploaded": True})

        ext = os.path.splitext(command.original_filename)[1]
        stored_filename = f"{uuid.uuid4().hex}{ext}"

        try:
            stored_path = self.storage.save(command.file_path, stored_filename)
        except Exception:
            with suppress(FileNotFoundError):
                os.remove(command.file_path)
            raise

        if self.file_mirror is not None:
            try:
                await self.file_mirror(stored_filename, stored_path)
            except Exception:
                self._cleanup_stored_file(stored_path)
                with suppress(FileNotFoundError):
                    os.remove(command.file_path)
                raise

        with suppress(FileNotFoundError):
            os.remove(command.file_path)

        metadata_dict = command.document_metadata or {}
        document_metadata = DocumentMetadata(**metadata_dict)

        entity = DocumentUpload(
            id=_new_id(),
            original_filename=command.original_filename,
            stored_filename=stored_filename,
            file_path=stored_path,
            file_size=command.file_size,
            mime_type=command.mime_type,
            extension=ext,
            checksum=checksum,
            content_type="document",
            uploaded_by=command.uploaded_by,
            organization_id=command.organization_id,
            store_id=command.store_id,
            knowledge_scope=command.knowledge_scope,
            status="uploaded",
            document_metadata=document_metadata,
            virus_scan_status="pending",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        try:
            created = await self.repository.create(entity)
        except ConcurrencyException:
            # A concurrent request inserted the same (checksum, store_id) first.
            # Drop the file we just stored and return the winning upload idempotently.
            self._cleanup_stored_file(stored_path)
            winner = await self.repository.find_by_checksum(checksum, store_id=command.store_id)
            if winner is not None:
                logger.info(
                    "Concurrent duplicate upload; returning winner",
                    extra={
                        "upload_id": winner.id,
                        "store_id": command.store_id,
                        "checksum": checksum[:16],
                    },
                )
                return self._to_dto(winner).model_copy(update={"already_uploaded": True})
            raise
        except Exception:
            self._cleanup_stored_file(stored_path)
            raise

        logger.info(
            "File uploaded",
            extra={
                "upload_id": created.id,
                "original_filename": created.original_filename,
                "file_size": created.file_size,
                "checksum": created.checksum[:16],
            },
        )
        return self._to_dto(created)

    def _cleanup_stored_file(self, stored_path: str) -> None:
        try:
            self.storage.delete(stored_path)
        except Exception:
            logger.debug("Stored file cleanup failed (already gone?): %s", stored_path)

    @staticmethod
    def _to_dto(entity: DocumentUpload) -> UploadDTO:
        from app.application.knowledge.dto.knowledge_dto import DocumentMetadataDTO

        return UploadDTO(
            id=entity.id,
            original_filename=entity.original_filename,
            stored_filename=entity.stored_filename,
            file_path=entity.file_path,
            file_size=entity.file_size,
            mime_type=entity.mime_type,
            extension=entity.extension,
            checksum=entity.checksum,
            content_type=entity.content_type,
            uploaded_by=entity.uploaded_by,
            organization_id=entity.organization_id,
            store_id=entity.store_id,
            knowledge_scope=entity.knowledge_scope,
            status=entity.status,
            document_metadata=DocumentMetadataDTO(**entity.document_metadata.model_dump()),
            virus_scan_status=entity.virus_scan_status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )
