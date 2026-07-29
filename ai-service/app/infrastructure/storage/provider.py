from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageProvider(ABC):
    """Abstract interface for file storage backends."""

    @abstractmethod
    def save(self, source_path: str, filename: str) -> str:
        """Persist a file and return the stored path.

        Args:
            source_path: Temporary path of the file to store.
            filename: Unique filename to use in storage.

        Returns:
            The stored file path or identifier.
        """

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Remove a stored file.

        Args:
            path: The stored file path or identifier to remove.

        Returns:
            True if the file was removed, False otherwise.
        """

    @abstractmethod
    def get_url(self, path: str) -> str:
        """Return a publicly accessible URL for the stored file.

        Args:
            path: The stored file path or identifier.

        Returns:
            A URL string.
        """

    @abstractmethod
    def open(self, path: str) -> BinaryIO:
        """Open a stored file for reading.

        Args:
            path: The stored file path or identifier.

        Returns:
            An open binary file handle.
        """
