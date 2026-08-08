"""MongoDB GridFS mirror for uploaded knowledge documents.

Uploaded files live on the API container's local disk, but ingestion runs on a
separate worker container that shares only MongoDB. Mirroring uploads into
GridFS lets the worker materialize the file locally before extraction.
"""

import logging
import os

from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from app.infrastructure.mongodb.client import get_mongodb

logger = logging.getLogger(__name__)

GRIDFS_BUCKET_NAME: str = "knowledge_uploads_files"


def _bucket() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(get_mongodb(), bucket_name=GRIDFS_BUCKET_NAME)


async def mirror_to_gridfs(stored_filename: str, local_path: str) -> None:
    """Store the local file into GridFS keyed by ``stored_filename``."""
    try:
        with open(local_path, "rb") as source:
            await _bucket().upload_from_stream(stored_filename, source)
        logger.info(
            "Mirrored upload into GridFS",
            extra={"stored_filename": stored_filename, "bucket": GRIDFS_BUCKET_NAME},
        )
    except Exception:
        logger.exception(
            "Failed to mirror upload into GridFS",
            extra={"stored_filename": stored_filename, "local_path": local_path},
        )
        raise


async def fetch_from_gridfs(stored_filename: str, dest_dir: str) -> str | None:
    """Materialize ``stored_filename`` from GridFS into ``dest_dir``.

    Returns the local path when the file existed and was written, None when it
    is not present in GridFS.
    """
    bucket = _bucket()
    try:
        grid_out = await bucket.open_download_stream_by_name(stored_filename)
    except Exception:
        logger.warning("File not present in GridFS: %s", stored_filename)
        return None

    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, stored_filename)
    temp_path = dest_path + ".tmp"
    try:
        with open(temp_path, "wb") as intermediate:
            while True:
                chunk = await grid_out.read(1024 * 1024)
                if not chunk:
                    break
                intermediate.write(chunk)
        os.replace(temp_path, dest_path)
        logger.info(
            "Materialized upload from GridFS",
            extra={"stored_filename": stored_filename, "local_path": dest_path},
        )
        return dest_path
    finally:
        grid_out.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def delete_from_gridfs(stored_filename: str) -> bool:
    """Remove ``stored_filename`` from GridFS, returning True when one was deleted."""
    bucket = _bucket()
    files_collection = get_mongodb()[f"{GRIDFS_BUCKET_NAME}.files"]
    try:
        file_doc = await files_collection.find_one({"filename": stored_filename})
        if file_doc is None:
            return False
        await bucket.delete(file_doc["_id"])
        logger.info(
            "Deleted upload from GridFS",
            extra={"stored_filename": stored_filename, "bucket": GRIDFS_BUCKET_NAME},
        )
        return True
    except Exception:
        logger.exception("Failed to delete upload from GridFS", extra={"stored_filename": stored_filename})
        return False
