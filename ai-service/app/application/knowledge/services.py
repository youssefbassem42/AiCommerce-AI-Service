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
)
from app.domain.knowledge.value_objects import DocumentMetadata, DocumentVersion


def _new_id() -> str:
    return str(ObjectId())


class KnowledgeDocumentService:
    """CRUD application service for knowledge documents."""

    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

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
            versions=[
                DocumentVersion(**version.model_dump(exclude_none=True))
                for version in data.versions
            ],
            current_version=data.current_version,
            chunking_strategy=data.chunking_strategy,
        )
        created = await self.repository.create(entity)
        return self._to_dto(created)

    async def get_by_id(self, document_id: str) -> KnowledgeDocumentDTO:
        entity = await self.repository.find_by_id(document_id)
        if entity is None:
            raise KnowledgeDocumentNotFoundException(
                f"Knowledge document '{document_id}' was not found."
            )
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
    ) -> KnowledgeDocumentDTO:
        entity = await self.repository.find_by_id(document_id)
        if entity is None:
            raise KnowledgeDocumentNotFoundException(
                f"Knowledge document '{document_id}' was not found."
            )

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
            entity.versions = [
                DocumentVersion(**version.model_dump(exclude_none=True))
                for version in data.versions
            ]
        if "current_version" in updates and data.current_version is not None:
            entity.current_version = data.current_version
        if "chunking_strategy" in updates and data.chunking_strategy is not None:
            entity.chunking_strategy = data.chunking_strategy

        entity.updated_at = datetime.now(UTC)
        updated = await self.repository.update(entity)
        return self._to_dto(updated)

    async def delete(self, document_id: str) -> bool:
        deleted = await self.repository.delete(document_id)
        if not deleted:
            raise KnowledgeDocumentNotFoundException(
                f"Knowledge document '{document_id}' was not found."
            )
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
            raise BusinessSummaryNotFoundException(
                f"Business summary '{summary_id}' was not found."
            )
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
            raise BusinessSummaryNotFoundException(
                f"Business summary '{summary_id}' was not found."
            )

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
            raise BusinessSummaryNotFoundException(
                f"Business summary '{summary_id}' was not found."
            )
        return deleted


class DocumentUploadService:
    """Application service for uploading documents to the knowledge base."""

    def __init__(
        self,
        repository: "UploadRepository",
        storage: "StorageProvider",
    ):
        self.repository = repository
        self.storage = storage

    async def upload(self, command: "UploadDocumentCommand") -> "UploadDTO":
        from app.application.knowledge.commands.upload_handler import UploadDocumentHandler

        handler = UploadDocumentHandler(repository=self.repository, storage=self.storage)
        return await handler.handle(command)

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
