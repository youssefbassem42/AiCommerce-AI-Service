import logging
import os
import shutil
from typing import BinaryIO

from app.infrastructure.storage.provider import StorageProvider

logger = logging.getLogger(__name__)


class LocalStorageProvider(StorageProvider):
    """Stores files on the local filesystem.

    Configuration is provided via the ``upload_dir`` constructor argument
    (defaulting to ``./uploads``).  Sub-directories are created on demand.
    """

    def __init__(self, upload_dir: str = "./uploads") -> None:
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)
        logger.info("LocalStorageProvider initialised", extra={"upload_dir": upload_dir})

    def save(self, source_path: str, filename: str) -> str:
        dest = os.path.join(self.upload_dir, filename)
        shutil.copy2(source_path, dest)
        logger.debug("File stored locally", extra={"source": source_path, "dest": dest})
        return dest

    def delete(self, path: str) -> bool:
        try:
            if os.path.isfile(path):
                os.remove(path)
                logger.debug("File deleted", extra={"path": path})
                return True
            logger.warning("File not found for deletion", extra={"path": path})
            return False
        except OSError as e:
            logger.error("Failed to delete file", extra={"path": path, "error": str(e)})
            return False

    def get_url(self, path: str) -> str:
        return f"file://{os.path.abspath(path)}"

    def open(self, path: str) -> BinaryIO:
        return open(path, "rb")
