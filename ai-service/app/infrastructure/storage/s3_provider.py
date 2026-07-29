"""S3-compatible storage provider (stub).

This module provides a placeholder implementation for S3-compatible object
storage.  Complete the ``save``, ``delete``, ``get_url``, and ``open``
methods with the actual S3 client (e.g. ``boto3``) when the backend is
ready for production use.
"""

import logging
from typing import BinaryIO

from app.infrastructure.storage.provider import StorageProvider

logger = logging.getLogger(__name__)


class S3StorageProvider(StorageProvider):
    """Placeholder for an S3-compatible object storage backend.

    TODO: Implement with ``boto3`` or ``aioboto3`` once the S3
    configuration (bucket name, region, credentials) is available.
    """

    def __init__(self, bucket: str = "knowledge-uploads") -> None:
        self.bucket = bucket
        logger.info(
            "S3StorageProvider initialised (stub)",
            extra={"bucket": bucket},
        )

    def save(self, source_path: str, filename: str) -> str:
        raise NotImplementedError("S3StorageProvider.save is not yet implemented")

    def delete(self, path: str) -> bool:
        raise NotImplementedError("S3StorageProvider.delete is not yet implemented")

    def get_url(self, path: str) -> str:
        raise NotImplementedError("S3StorageProvider.get_url is not yet implemented")

    def open(self, path: str) -> BinaryIO:
        raise NotImplementedError("S3StorageProvider.open is not yet implemented")
