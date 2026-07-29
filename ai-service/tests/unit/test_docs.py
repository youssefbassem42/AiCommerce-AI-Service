import os

import pytest

DOCS_DIR = "docs"


@pytest.mark.unit
class TestDocs:
    def test_docs_directory_exists(self):
        assert os.path.isdir(DOCS_DIR), "docs/ directory not found"

    def test_all_docs_have_content(self):
        empty = []
        for fname in os.listdir(DOCS_DIR):
            if fname.endswith(".md"):
                path = os.path.join(DOCS_DIR, fname)
                if os.path.getsize(path) == 0:
                    empty.append(fname)
        assert not empty, f"Empty doc files: {empty}"

    def test_critical_docs_exist(self):
        critical = ["agents.md", "rag.md", "database.md", "deployment.md", "security.md", "ARCHITECTURE.md"]
        for doc in critical:
            path = os.path.join(DOCS_DIR, doc)
            assert os.path.exists(path), f"Missing critical doc: {doc}"
            assert os.path.getsize(path) > 0, f"Empty critical doc: {doc}"
