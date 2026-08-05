"""File-path validation for document ingestion.

Guards against local file inclusion (LFI): a `file_path`/`source_url` is only
accepted when it is an allowed document extension resolved inside an allowed
ingestion root (system temp dir or the configured upload location). Paths with
URL schemes, traversal segments, null bytes or symlinks escaping the allowed
roots are rejected.
"""

import os
import tempfile
from pathlib import Path

from app.core.knowledge_settings import knowledge_settings

ALLOWED_DOCUMENT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".txt",
        ".md",
        ".markdown",
        ".pdf",
        ".docx",
        ".doc",
        ".csv",
        ".rtf",
        ".html",
        ".htm",
        ".json",
        ".xml",
    }
)


def _allowed_roots() -> set[str]:
    roots = {
        os.path.realpath(tempfile.gettempdir()),
        os.path.realpath(knowledge_settings.upload_local_path),
        os.path.realpath(os.path.join(os.getcwd(), knowledge_settings.upload_local_path)),
    }
    return {root for root in roots if root}


def is_safe_document_path(file_path: str | None) -> bool:
    """Return True when ``file_path`` is a safe local file for ingestion."""
    if not file_path or not isinstance(file_path, str):
        return False
    path = file_path.strip()
    if not path or "\x00" in path:
        return False
    if "://" in path:
        return False
    if ".." in Path(path).parts:
        return False
    extension = os.path.splitext(path)[1].lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        return False
    resolved = os.path.realpath(os.path.abspath(path))
    return any(resolved == root or resolved.startswith(root + os.sep) for root in _allowed_roots())
