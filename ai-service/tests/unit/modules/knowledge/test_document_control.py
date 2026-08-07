from contextlib import contextmanager
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
        status="processing",
        versions=[DocumentVersion(version_number=1, is_current=True, checksum="a" * 64)],
    )


class TestDocumentUploadBridge:
    @staticmethod
    def _service(upload_repo=None, storage=None, knowledge_repo=None, chunk_repo=None):
        return DocumentUploadService(
            repository=upload_repo or MagicMock(),
            storage=storage or MagicMock(),
            knowledge_repository=knowledge_repo,
            chunk_repository=chunk_repo,
        )

    @contextmanager
    def _patch_tasks(self):
        with (
            patch("app.workers.ingestion.tasks.process_document_task") as mock_proc,
            patch("app.workers.ingestion.tasks.generate_chunks_task") as mock_chunks,
        ):
            yield mock_proc, mock_chunks

    async def test_upload_creates_knowledge_document(self) -> None:
        knowledge_repo = MagicMock()
        knowledge_repo.find_by_store_and_category = AsyncMock(return_value=[])
        service = self._service(knowledge_repo=knowledge_repo)

        result_upload = UploadDTO(**_upload_entity().model_dump())
        created_doc = _document_entity(document_id="doc-1")

        with (
            patch(
                "app.application.knowledge.commands.upload_handler.UploadDocumentHandler",
                autospec=True,
            ) as mock_handler_cls,
            self._patch_tasks() as (mock_proc, mock_chunks),
        ):
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
        assert dto.content_changed is True
        mock_proc.delay.assert_called_once()
        mock_chunks.delay.assert_called_once()

    async def test_upload_without_knowledge_repo_returns_no_document_id(self) -> None:
        service = self._service()
        payload = UploadDTO(**_upload_entity().model_dump())
        with patch(
            "app.application.knowledge.commands.upload_handler.UploadDocumentHandler",
            autospec=True,
        ) as mock_handler_cls:
            handler = mock_handler_cls.return_value
            handler.handle = AsyncMock(return_value=payload)
            result = await service.upload(MagicMock())
        assert result.document_id is None
        assert result.already_uploaded is False

    async def test_upload_same_file_returns_existing_already_uploaded(self) -> None:
        knowledge_repo = MagicMock()
        knowledge_repo.find_by_source_uri = AsyncMock(return_value=None)
        knowledge_repo.find_by_store_and_category = AsyncMock(return_value=[_document_entity(document_id="doc-1")])
        service = self._service(knowledge_repo=knowledge_repo)

        payload = UploadDTO(
            **_upload_entity().model_dump(),
            already_uploaded=True,
        )

        with (
            patch(
                "app.application.knowledge.commands.upload_handler.UploadDocumentHandler",
                autospec=True,
            ) as mock_handler_cls,
            self._patch_tasks() as (mock_proc, mock_chunks),
        ):
            handler = mock_handler_cls.return_value
            handler.handle = AsyncMock(return_value=payload)
            result = await service.upload(MagicMock())

        assert result.already_uploaded is True
        assert result.document_id == "doc-1"
        knowledge_repo.find_by_store_and_category.assert_awaited_once_with(
            store_id="store-1", category="general", limit=1
        )
        knowledge_repo.create.assert_not_called()
        mock_proc.delay.assert_not_called()
        mock_chunks.delay.assert_not_called()

    async def test_reupload_different_file_bumps_existing_document_version(self) -> None:
        existing = _document_entity(
            document_id="doc-1",
            source_url="./uploads/old.txt",
        )
        existing.status = "active"
        existing.processed_text = "old content"
        existing.versions = [DocumentVersion(version_number=1, is_current=True, checksum="a" * 64)]

        knowledge_repo = MagicMock()
        knowledge_repo.find_by_store_and_category = AsyncMock(return_value=[existing])
        knowledge_repo.update = AsyncMock(return_value=existing)
        storage = MagicMock()
        chunk_repo = MagicMock()
        chunk_repo.delete_by_document_id = AsyncMock(return_value=3)
        service = self._service(
            storage=storage,
            knowledge_repo=knowledge_repo,
            chunk_repo=chunk_repo,
        )

        new_upload = UploadDTO(**_upload_entity().model_dump())
        new_upload.checksum = "b" * 64
        new_upload.file_path = "./uploads/new.txt"

        with (
            patch(
                "app.application.knowledge.commands.upload_handler.UploadDocumentHandler",
                autospec=True,
            ) as mock_handler_cls,
            self._patch_tasks() as (mock_proc, mock_chunks),
        ):
            handler = mock_handler_cls.return_value
            handler.handle = AsyncMock(return_value=new_upload)
            result = await service.upload(MagicMock())

        assert result.document_id == "doc-1"
        assert result.content_changed is True
        assert result.already_uploaded is False
        storage.delete.assert_called_once_with("./uploads/old.txt")
        chunk_repo.delete_by_document_id.assert_awaited_once_with("doc-1")
        knowledge_repo.update.assert_awaited_once()
        assert existing.current_version == 2
        assert len(existing.versions) == 2
        assert existing.versions[0].is_current is False
        assert existing.versions[1].checksum == "b" * 64
        assert existing.versions[1].is_current is True
        assert existing.status == "processing"
        assert existing.processed_text is None
        assert existing.source_url == "./uploads/new.txt"
        assert existing.metadata.category == "general"
        mock_proc.delay.assert_called_once()
        mock_chunks.delay.assert_called_once()


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
