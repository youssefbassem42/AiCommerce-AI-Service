from abc import ABC, abstractmethod
from typing import Optional

from app.domain.knowledge.entities.document_upload import DocumentUpload
from app.shared.kernel.repository import AsyncRepository


class UploadRepository(AsyncRepository[DocumentUpload, str], ABC):
    """Domain repository interface for document uploads."""

    @abstractmethod
    async def find_by_checksum(self, checksum: str) -> Optional[DocumentUpload]:
        """Find an upload by its SHA-256 checksum to detect duplicates."""

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
