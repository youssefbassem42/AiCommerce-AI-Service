import logging
import os
from datetime import UTC, datetime

from bson import ObjectId

from app.application.knowledge.dto import (
    BusinessSummaryCreateDTO,
    BusinessSummaryDTO,
    BusinessSummaryUpdateDTO,
    DocumentMetadataDTO,
    DocumentVersionDTO,
    KnowledgeChunkCreateDTO,
    KnowledgeChunkDTO,
    KnowledgeChunkUpdateDTO,
    KnowledgeDocumentCreateDTO,
    KnowledgeDocumentDTO,
    KnowledgeDocumentUpdateDTO,
    PaginatedResultDTO,
)
from app.domain.knowledge.entities import BusinessSummary, KnowledgeChunk, KnowledgeDocument
from app.domain.knowledge.exceptions import (
    BusinessSummaryNotFoundException,
    KnowledgeChunkNotFoundException,
    KnowledgeDocumentNotFoundException,
)
from app.domain.knowledge.repositories import (
    BusinessSummaryRepository,
    ChunkRepository,
    KnowledgeRepository,
    UploadRepository,
)
from app.domain.knowledge.value_objects import DocumentMetadata, DocumentVersion


def _new_id() -> str:
    return str(ObjectId())


logger = logging.getLogger(__name__)


class KnowledgeDocumentService:
    """CRUD application service for knowledge documents."""

    def __init__(
        self,
        repository: KnowledgeRepository,
        storage: "StorageProvider | None" = None,
        upload_repository: "UploadRepository | None" = None,
        chunk_repository: "ChunkRepository | None" = None,
    ):
        self.repository = repository
        self.storage = storage
        self.upload_repository = upload_repository
        self.chunk_repository = chunk_repository

    async def create(self, data: KnowledgeDocumentCreateDTO) -> KnowledgeDocumentDTO:
        entity = KnowledgeDocument(
            id=_new_id(),
            store_id=data.store_id,
            title=data.title,
            description=data.description,
            source_url=data.source_url,
            status=data.status,
            language=data.language,
            metadata=DocumentMetadata(**data.metadata.model_dump()),
            versions=[DocumentVersion(**version.model_dump(exclude_none=True)) for version in data.versions],
            current_version=data.current_version,
            chunking_strategy=data.chunking_strategy,
        )
        created = await self.repository.create(entity)
        return self._to_dto(created)

    async def get_by_id(self, document_id: str) -> KnowledgeDocumentDTO:
        entity = await self.repository.find_by_id(document_id)
        if entity is None:
            raise KnowledgeDocumentNotFoundException(f"Knowledge document '{document_id}' was not found.")
        return self._to_dto(entity)

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        store_id: str | None = None,
        status: str | None = None,
    ) -> PaginatedResultDTO[KnowledgeDocumentDTO]:
        filters: dict[str, str] = {}
        if store_id:
            filters["store_id"] = store_id
        if status:
            filters["status"] = status
        items, total = await self.repository.paginate(filters=filters, page=page, page_size=page_size)
        return PaginatedResultDTO[KnowledgeDocumentDTO](
            items=[self._to_dto(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(
        self,
        document_id: str,
        data: KnowledgeDocumentUpdateDTO,
        owner_store_id: str | None = None,
    ) -> KnowledgeDocumentDTO:
        entity = await self.repository.find_by_id(document_id)
        if entity is None:
            raise KnowledgeDocumentNotFoundException(f"Knowledge document '{document_id}' was not found.")
        if owner_store_id is not None and entity.store_id != owner_store_id:
            raise KnowledgeDocumentNotFoundException(f"Knowledge document '{document_id}' was not found.")

        updates = data.model_dump(exclude_unset=True)
        if "store_id" in updates and data.store_id is not None:
            entity.store_id = data.store_id
        if "title" in updates and data.title is not None:
            entity.title = data.title
        if "description" in updates:
            entity.description = data.description
        if "source_url" in updates:
            entity.source_url = data.source_url
        if "status" in updates and data.status is not None:
            entity.status = data.status
        if "language" in updates and data.language is not None:
            entity.language = data.language
        if "metadata" in updates and data.metadata is not None:
            entity.metadata = DocumentMetadata(**data.metadata.model_dump())
        if "versions" in updates and data.versions is not None:
            entity.versions = [DocumentVersion(**version.model_dump(exclude_none=True)) for version in data.versions]
        if "current_version" in updates and data.current_version is not None:
            entity.current_version = data.current_version
        if "chunking_strategy" in updates and data.chunking_strategy is not None:
            entity.chunking_strategy = data.chunking_strategy

        entity.updated_at = datetime.now(UTC)
        updated = await self.repository.update(entity)
        return self._to_dto(updated)

    async def delete(self, document_id: str, owner_store_id: str | None = None) -> bool:
        entity = await self.repository.find_by_id(document_id)
        if entity is None:
            raise KnowledgeDocumentNotFoundException(f"Knowledge document '{document_id}' was not found.")
        if owner_store_id is not None and entity.store_id != owner_store_id:
            raise KnowledgeDocumentNotFoundException(f"Knowledge document '{document_id}' was not found.")

        if self.storage is not None and entity.source_url:
            self.storage.delete(entity.source_url)

        if self.upload_repository is not None and entity.source_url:
            stored_filename = os.path.basename(entity.source_url)
            upload = await self.upload_repository.find_by_stored_filename(stored_filename)
            if upload is not None:
                await self.upload_repository.delete(upload.id)

        if self.chunk_repository is not None:
            await self.chunk_repository.delete_by_document_id(document_id)

        deleted = await self.repository.delete(document_id)
        return deleted

    @staticmethod
    def _to_dto(entity: KnowledgeDocument) -> KnowledgeDocumentDTO:
        return KnowledgeDocumentDTO(
            id=entity.id,
            store_id=entity.store_id,
            title=entity.title,
            description=entity.description,
            source_url=entity.source_url,
            status=entity.status,
            language=entity.language,
            metadata=DocumentMetadataDTO(**entity.metadata.model_dump()),
            versions=[DocumentVersionDTO(**version.model_dump()) for version in entity.versions],
            current_version=entity.current_version,
            chunks=[
                KnowledgeChunkDTO(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    version_number=chunk.version_number,
                    chunk_index=chunk.chunk_index,
                    title=chunk.title,
                    content=chunk.content,
                    embedding_id=chunk.embedding_id,
                    metadata=chunk.metadata,
                    created_at=chunk.created_at,
                    updated_at=chunk.updated_at,
                )
                for chunk in entity.chunks
            ],
            chunking_strategy=entity.chunking_strategy,
            processed_text=entity.processed_text,
            page_count=entity.page_count,
            word_count=entity.word_count,
            char_count=entity.char_count,
            estimated_tokens=entity.estimated_tokens,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )


class KnowledgeChunkService:
    """CRUD application service for knowledge chunks."""

    def __init__(self, repository: ChunkRepository):
        self.repository = repository

    async def create(self, data: KnowledgeChunkCreateDTO) -> KnowledgeChunkDTO:
        entity = KnowledgeChunk(
            id=_new_id(),
            document_id=data.document_id,
            version_number=data.version_number,
            chunk_index=data.chunk_index,
            title=data.title,
            content=data.content,
            embedding_id=data.embedding_id,
            metadata=data.metadata,
        )
        created = await self.repository.create(entity)
        return KnowledgeChunkDTO(**created.model_dump())

    async def get_by_id(self, chunk_id: str) -> KnowledgeChunkDTO:
        entity = await self.repository.find_by_id(chunk_id)
        if entity is None:
            raise KnowledgeChunkNotFoundException(f"Knowledge chunk '{chunk_id}' was not found.")
        return KnowledgeChunkDTO(**entity.model_dump())

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        document_id: str | None = None,
        version_number: int | None = None,
    ) -> PaginatedResultDTO[KnowledgeChunkDTO]:
        filters: dict[str, str | int] = {}
        if document_id:
            filters["document_id"] = document_id
        if version_number is not None:
            filters["version_number"] = version_number
        items, total = await self.repository.paginate(filters=filters, page=page, page_size=page_size)
        return PaginatedResultDTO[KnowledgeChunkDTO](
            items=[KnowledgeChunkDTO(**item.model_dump()) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(self, chunk_id: str, data: KnowledgeChunkUpdateDTO) -> KnowledgeChunkDTO:
        entity = await self.repository.find_by_id(chunk_id)
        if entity is None:
            raise KnowledgeChunkNotFoundException(f"Knowledge chunk '{chunk_id}' was not found.")

        updates = data.model_dump(exclude_unset=True)
        if "version_number" in updates and data.version_number is not None:
            entity.version_number = data.version_number
        if "chunk_index" in updates and data.chunk_index is not None:
            entity.chunk_index = data.chunk_index
        if "title" in updates:
            entity.title = data.title
        if "content" in updates and data.content is not None:
            entity.content = data.content
        if "embedding_id" in updates:
            entity.embedding_id = data.embedding_id
        if "metadata" in updates and data.metadata is not None:
            entity.metadata = data.metadata

        entity.updated_at = datetime.now(UTC)
        updated = await self.repository.update(entity)
        return KnowledgeChunkDTO(**updated.model_dump())

    async def delete(self, chunk_id: str) -> bool:
        deleted = await self.repository.delete(chunk_id)
        if not deleted:
            raise KnowledgeChunkNotFoundException(f"Knowledge chunk '{chunk_id}' was not found.")
        return deleted


class BusinessSummaryService:
    """CRUD application service for business summaries."""

    def __init__(self, repository: BusinessSummaryRepository):
        self.repository = repository

    async def create(self, data: BusinessSummaryCreateDTO) -> BusinessSummaryDTO:
        entity = BusinessSummary(
            id=_new_id(),
            document_id=data.document_id,
            version_number=data.version_number,
            title=data.title,
            summary=data.summary,
            metadata=data.metadata,
        )
        created = await self.repository.create(entity)
        return BusinessSummaryDTO(**created.model_dump())

    async def get_by_id(self, summary_id: str) -> BusinessSummaryDTO:
        entity = await self.repository.find_by_id(summary_id)
        if entity is None:
            raise BusinessSummaryNotFoundException(f"Business summary '{summary_id}' was not found.")
        return BusinessSummaryDTO(**entity.model_dump())

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        document_id: str | None = None,
        version_number: int | None = None,
    ) -> PaginatedResultDTO[BusinessSummaryDTO]:
        filters: dict[str, str | int] = {}
        if document_id:
            filters["document_id"] = document_id
        if version_number is not None:
            filters["version_number"] = version_number
        items, total = await self.repository.paginate(filters=filters, page=page, page_size=page_size)
        return PaginatedResultDTO[BusinessSummaryDTO](
            items=[BusinessSummaryDTO(**item.model_dump()) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(self, summary_id: str, data: BusinessSummaryUpdateDTO) -> BusinessSummaryDTO:
        entity = await self.repository.find_by_id(summary_id)
        if entity is None:
            raise BusinessSummaryNotFoundException(f"Business summary '{summary_id}' was not found.")

        updates = data.model_dump(exclude_unset=True)
        if "version_number" in updates and data.version_number is not None:
            entity.version_number = data.version_number
        if "title" in updates and data.title is not None:
            entity.title = data.title
        if "summary" in updates and data.summary is not None:
            entity.summary = data.summary
        if "metadata" in updates and data.metadata is not None:
            entity.metadata = data.metadata

        entity.updated_at = datetime.now(UTC)
        updated = await self.repository.update(entity)
        return BusinessSummaryDTO(**updated.model_dump())

    async def delete(self, summary_id: str) -> bool:
        deleted = await self.repository.delete(summary_id)
        if not deleted:
            raise BusinessSummaryNotFoundException(f"Business summary '{summary_id}' was not found.")
        return deleted


class DocumentUploadService:
    """Application service for uploading documents to the knowledge base."""

    def __init__(
        self,
        repository: "UploadRepository",
        storage: "StorageProvider",
        knowledge_repository: "KnowledgeRepository | None" = None,
        chunk_repository: "ChunkRepository | None" = None,
    ):
        self.repository = repository
        self.storage = storage
        self.knowledge_repository = knowledge_repository
        self.chunk_repository = chunk_repository

    async def upload(self, command: "UploadDocumentCommand") -> "UploadDTO":
        from app.application.knowledge.commands.upload_handler import UploadDocumentHandler

        handler = UploadDocumentHandler(repository=self.repository, storage=self.storage)
        result = await handler.handle(command)

        if result.already_uploaded:
            # Idempotent re-upload: same store + same content -> no new version.
            if self.knowledge_repository is not None:
                doc = await self.knowledge_repository.find_by_source_uri(result.id)
                if doc is None and result.store_id:
                    docs = await self.knowledge_repository.find_by_store_and_category(
                        store_id=result.store_id,
                        category=result.knowledge_scope,
                        limit=1,
                    )
                    doc = docs[0] if docs else None
                if doc is not None:
                    result = result.model_copy(update={"document_id": doc.id})
            return result

        if self.knowledge_repository is not None:
            document_id, changed = await self._create_or_update_knowledge_document(result)
            result = result.model_copy(update={"document_id": document_id, "content_changed": changed})
            if changed:
                self._enqueue_reprocess(result)

        return result

    async def _create_or_update_knowledge_document(self, upload: "UploadDTO") -> tuple[str, bool]:
        """Create a knowledge document for the upload, or bump the store's existing one.

        Versioning is scoped per store + knowledge category (e.g. FAQ): a store that
        uploads a new file for the same category replaces the previous file, increments
        the document version so RAG context stays current. Returns (document_id, changed).
        """
        from app.application.knowledge.dto.knowledge_dto import DocumentMetadataDTO
        from app.domain.knowledge.entities import KnowledgeDocument

        existing = await self._find_document_for_scope(upload)

        stored_metadata = upload.document_metadata or DocumentMetadataDTO()
        if existing is not None:
            return await self._bump_document_version(existing, upload)

        document_metadata = DocumentMetadata(
            source_type="upload",
            source_uri=upload.id,
            mime_type=upload.mime_type,
            language=stored_metadata.language,
            category=upload.knowledge_scope,
            tags=stored_metadata.tags or [upload.knowledge_scope],
            attributes={"checksum": upload.checksum, "upload_id": upload.id},
        )

        document = KnowledgeDocument(
            id=_new_id(),
            store_id=upload.store_id,
            title=upload.original_filename,
            description=f"Uploaded {upload.knowledge_scope} knowledge document (source: {upload.original_filename}).",
            source_url=upload.file_path,
            status="draft",
            language=stored_metadata.language,
            metadata=document_metadata,
            versions=[
                DocumentVersion(
                    version_number=1,
                    checksum=upload.checksum,
                    created_by=upload.uploaded_by,
                    is_current=True,
                )
            ],
            current_version=1,
            chunking_strategy="manual",
            updated_at=datetime.now(UTC),
        )
        created = await self.knowledge_repository.create(document)
        logger.info(
            "Knowledge document created for upload",
            extra={"upload_id": upload.id, "document_id": created.id, "store_id": upload.store_id},
        )
        return created.id, True

    async def _find_document_for_scope(self, upload: "UploadDTO") -> KnowledgeDocument | None:
        if not upload.store_id:
            return None
        docs = await self.knowledge_repository.find_by_store_and_category(
            store_id=upload.store_id,
            category=upload.knowledge_scope,
            limit=50,
        )
        return docs[0] if docs else None

    async def _bump_document_version(
        self,
        existing: KnowledgeDocument,
        upload: "UploadDTO",
    ) -> tuple[str, bool]:
        """Replace content of the store's existing document and create the next version."""
        if self.storage is not None and existing.source_url:
            self.storage.delete(existing.source_url)

        if self.chunk_repository is not None:
            await self.chunk_repository.delete_by_document_id(existing.id)

        next_version = max((v.version_number for v in existing.versions), default=0) + 1
        stored_metadata = upload.document_metadata
        old_metadata = existing.metadata

        for version in existing.versions:
            version.is_current = False

        existing.versions.append(
            DocumentVersion(
                version_number=next_version,
                checksum=upload.checksum,
                created_by=upload.uploaded_by,
                notes=f"Re-upload replaced previous version (source: {upload.original_filename})",
                is_current=True,
            )
        )
        existing.current_version = next_version
        existing.source_url = upload.file_path
        existing.status = "draft"
        existing.processed_text = None
        existing.page_count = None
        existing.word_count = None
        existing.char_count = None
        existing.estimated_tokens = None
        existing.metadata = DocumentMetadata(
            source_type="upload",
            source_uri=upload.id,
            mime_type=upload.mime_type,
            language=stored_metadata.language if stored_metadata else old_metadata.language,
            category=upload.knowledge_scope,
            tags=stored_metadata.tags if stored_metadata else old_metadata.tags,
            attributes={"checksum": upload.checksum, "upload_id": upload.id},
        )
        existing.updated_at = datetime.now(UTC)

        updated = await self.knowledge_repository.update(existing)
        logger.info(
            "Bumped version of knowledge document for re-upload",
            extra={
                "document_id": updated.id,
                "store_id": updated.store_id,
                "version": next_version,
                "upload_id": upload.id,
            },
        )
        return updated.id, True

    def _enqueue_reprocess(self, upload: "UploadDTO") -> None:
        """Background refresh so the store's RAG policies/context reflect the new content."""
        if not upload.document_id:
            return
        try:
            from app.workers.ingestion.tasks import generate_chunks_task, process_document_task

            process_document_task.delay(
                document_id=upload.document_id,
                file_path=upload.file_path or "",
                mime_type=upload.mime_type,
                job_id=None,
            )
            generate_chunks_task.delay(
                document_id=upload.document_id,
                strategy="recursive_character",
                chunk_size=1000,
                overlap=200,
                job_id=None,
            )
        except Exception:
            logger.exception("Failed to enqueue auto re-process for document %s", upload.document_id)

    async def get_by_id(self, upload_id: str) -> "UploadDTO":
        from app.application.knowledge.dto.upload_dto import UploadDTO
        from app.domain.knowledge.exceptions import UploadNotFoundException

        entity = await self.repository.find_by_id(upload_id)
        if entity is None:
            raise UploadNotFoundException(f"Upload '{upload_id}' was not found.")
        return UploadDTO(**entity.model_dump())

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        store_id: str | None = None,
    ) -> "PaginatedResultDTO[UploadDTO]":
        from app.application.knowledge.dto.knowledge_dto import PaginatedResultDTO
        from app.application.knowledge.dto.upload_dto import UploadDTO

        filters: dict = {}
        if store_id:
            filters["store_id"] = store_id

        items, total = await self.repository.paginate(filters, page=page, page_size=page_size)
        return PaginatedResultDTO[UploadDTO](
            items=[UploadDTO(**entity.model_dump()) for entity in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def delete(self, upload_id: str) -> bool:
        from app.domain.knowledge.exceptions import UploadNotFoundException

        entity = await self.repository.find_by_id(upload_id)
        if entity is None:
            raise UploadNotFoundException(f"Upload '{upload_id}' was not found.")
        self.storage.delete(entity.file_path)
        return await self.repository.delete(upload_id)
