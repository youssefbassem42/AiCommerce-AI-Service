import os
import tempfile

from app.core.path_validation import ALLOWED_DOCUMENT_EXTENSIONS, is_safe_document_path


class TestIsSafeDocumentPath:
    def test_accepts_file_in_temp_dir(self):
        assert is_safe_document_path(os.path.join(tempfile.gettempdir(), "doc.pdf"))

    def test_rejects_path_traversal(self):
        assert not is_safe_document_path("/tmp/../etc/passwd")

    def test_rejects_absolute_sensitive_file(self):
        assert not is_safe_document_path("/etc/passwd")

    def test_rejects_env_file(self):
        assert not is_safe_document_path(os.path.join(tempfile.gettempdir(), ".env"))

    def test_rejects_disallowed_extension(self):
        assert not is_safe_document_path(os.path.join(tempfile.gettempdir(), "app.py"))

    def test_rejects_url_scheme(self):
        assert not is_safe_document_path("file:///etc/passwd")
        assert not is_safe_document_path("https://example.com/doc.pdf")

    def test_rejects_null_byte(self):
        assert not is_safe_document_path("/tmp/doc\x00.pdf")

    def test_rejects_empty_and_none(self):
        assert not is_safe_document_path("")
        assert not is_safe_document_path(None)

    def test_rejects_path_outside_allowed_roots(self):
        assert not is_safe_document_path(os.path.join(os.path.expanduser("~"), "private.pdf"))

    def test_allowed_extensions_are_document_types(self):
        assert "pdf" and "txt" in {ext.lstrip(".") for ext in ALLOWED_DOCUMENT_EXTENSIONS}
