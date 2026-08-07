from abc import ABC, abstractmethod

from app.domain.knowledge.entities.document_upload import DocumentUpload
from app.shared.kernel.repository import AsyncRepository


class UploadRepository(AsyncRepository[DocumentUpload, str], ABC):
    """Domain repository interface for document uploads."""

    @abstractmethod
    async def find_by_checksum(self, checksum: str, store_id: str | None = None) -> DocumentUpload | None:
        """Find an upload by its SHA-256 checksum.

        When ``store_id`` is provided the lookup is scoped to that store so duplicate
        detection is tenant-isolated (each store may upload its own copy of a file).
        """

    @abstractmethod
    async def find_by_store_id(
        self,
        store_id: str,
        limit: int = 20,
        skip: int = 0,
    ) -> list[DocumentUpload]:
        """Find uploads belonging to a store."""

    @abstractmethod
    async def find_by_status(
        self,
        status: str,
        limit: int = 20,
        skip: int = 0,
    ) -> list[DocumentUpload]:
        """Find uploads by status."""

    @abstractmethod
    async def find_by_stored_filename(self, stored_filename: str) -> DocumentUpload | None:
        """Find an upload by its stored (unique) filename."""
