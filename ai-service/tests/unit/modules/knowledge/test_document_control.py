from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.knowledge.dto import KnowledgeDocumentUpdateDTO, UploadDTO
from app.application.knowledge.services import DocumentUploadService, KnowledgeDocumentService
from app.domain.knowledge.entities import DocumentUpload, KnowledgeDocument
from app.domain.knowledge.exceptions import KnowledgeDocumentNotFoundException
from app.domain.knowledge.value_objects import DocumentVersion


def _upload_entity(
    upload_id: str = "upload-1",
    stored_filename: str = "abc123.txt",
    file_path: str = "./uploads/abc123.txt",
    store_id: str = "store-1",
) -> DocumentUpload:
    return DocumentUpload(
        id=upload_id,
        original_filename="faq.txt",
        stored_filename=stored_filename,
        file_path=file_path,
        file_size=42,
        mime_type="text/plain",
        extension=".txt",
        checksum="a" * 64,
        content_type="document",
        uploaded_by="user-1",
        store_id=store_id,
        knowledge_scope="general",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _document_entity(
    document_id: str = "doc-1",
    store_id: str = "store-1",
    source_url: str = "./uploads/abc123.txt",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=document_id,
        store_id=store_id,
        title="faq.txt",
        source_url=source_url,
        status="draft",
        versions=[DocumentVersion(version_number=1, is_current=True, checksum="a" * 64)],
    )


class TestDocumentUploadBridge:
    async def test_upload_creates_knowledge_document(self) -> None:
        upload_repo = MagicMock()
        storage = MagicMock()
        knowledge_repo = MagicMock()
        service = DocumentUploadService(
            repository=upload_repo,
            storage=storage,
            knowledge_repository=knowledge_repo,
        )

        result_upload = UploadDTO(**_upload_entity().model_dump())
        created_doc = _document_entity(document_id="doc-1")

        with patch(
            "app.application.knowledge.commands.upload_handler.UploadDocumentHandler",
            autospec=True,
        ) as mock_handler_cls:
            handler = mock_handler_cls.return_value
            handler.handle = AsyncMock(return_value=result_upload)
            knowledge_repo.create = AsyncMock(return_value=created_doc)

            dto = await service.upload(MagicMock())

        handler.handle.assert_awaited_once()
        knowledge_repo.create.assert_awaited_once()
        created = knowledge_repo.create.await_args.args[0]
        assert isinstance(created, KnowledgeDocument)
        assert created.store_id == "store-1"
        assert created.source_url == "./uploads/abc123.txt"
        assert created.metadata.source_type == "upload"
        assert created.metadata.source_uri == "upload-1"
        assert created.metadata.category == "general"
        assert created.versions[0].checksum == "a" * 64
        assert dto.document_id == "doc-1"

    async def test_upload_without_knowledge_repo_returns_no_document_id(self) -> None:
        service = DocumentUploadService(repository=MagicMock(), storage=MagicMock())
        payload = UploadDTO(**_upload_entity().model_dump())
        with patch(
            "app.application.knowledge.commands.upload_handler.UploadDocumentHandler",
            autospec=True,
        ) as mock_handler_cls:
            handler = mock_handler_cls.return_value
            handler.handle = AsyncMock(return_value=payload)
            result = await service.upload(MagicMock())
        assert result.document_id is None


class TestKnowledgeDocumentDelete:
    @staticmethod
    def _build_service():
        repo = MagicMock()
        storage = MagicMock()
        upload_repo = MagicMock()
        chunk_repo = MagicMock()
        upload = _upload_entity()
        upload_repo.find_by_stored_filename = AsyncMock(return_value=upload)
        upload_repo.delete = AsyncMock(return_value=True)
        chunk_repo.delete_by_document_id = AsyncMock(return_value=7)
        storage.delete = MagicMock(return_value=True)
        repo.delete = AsyncMock(return_value=True)
        service = KnowledgeDocumentService(
            repository=repo,
            storage=storage,
            upload_repository=upload_repo,
            chunk_repository=chunk_repo,
        )
        return service, repo, storage, upload_repo, chunk_repo

    async def test_delete_cascades_file_upload_and_chunks(self) -> None:
        service, repo, storage, upload_repo, chunk_repo = self._build_service()
        repo.find_by_id = AsyncMock(return_value=_document_entity())

        deleted = await service.delete("doc-1")

        assert deleted is True
        storage.delete.assert_called_once_with("./uploads/abc123.txt")
        upload_repo.find_by_stored_filename.assert_awaited_once_with("abc123.txt")
        upload_repo.delete.assert_awaited_once_with("upload-1")
        chunk_repo.delete_by_document_id.assert_awaited_once_with("doc-1")
        repo.delete.assert_awaited_once_with("doc-1")

    async def test_delete_missing_document_raises(self) -> None:
        service, repo, _, _, _ = self._build_service()
        repo.find_by_id = AsyncMock(return_value=None)
        with pytest.raises(KnowledgeDocumentNotFoundException):
            await service.delete("doc-x")

    async def test_delete_other_store_raises(self) -> None:
        service, repo, storage, _, chunk_repo = self._build_service()
        repo.find_by_id = AsyncMock(return_value=_document_entity(store_id="store-2"))
        with pytest.raises(KnowledgeDocumentNotFoundException):
            await service.delete("doc-1", owner_store_id="store-1")
        storage.delete.assert_not_called()
        chunk_repo.delete_by_document_id.assert_not_called()
        repo.delete.assert_not_called()


class TestKnowledgeDocumentUpdate:
    async def test_update_owner_guard(self) -> None:
        repo = MagicMock()
        repo.find_by_id = AsyncMock(return_value=_document_entity(store_id="store-2"))
        service = KnowledgeDocumentService(repository=repo)
        with pytest.raises(KnowledgeDocumentNotFoundException):
            await service.update(
                "doc-1",
                KnowledgeDocumentUpdateDTO(title="updated"),
                owner_store_id="store-1",
            )

    async def test_update_allowed_for_owner(self) -> None:
        repo = MagicMock()
        repo.find_by_id = AsyncMock(return_value=_document_entity())
        repo.update = AsyncMock(return_value=_document_entity())
        service = KnowledgeDocumentService(repository=repo)
        result = await service.update(
            "doc-1",
            KnowledgeDocumentUpdateDTO(title="updated"),
            owner_store_id="store-1",
        )
        assert result.title == "faq.txt"
        repo.update.assert_awaited_once()
