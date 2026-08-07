"""End-to-end verification of knowledge document control against a local MongoDB.

Runs the real FastAPI app (no dependency overrides) with an isolated database and a
temporary uploads directory, driving the HTTP contract:

  POST   /api/v1/knowledge-base/upload
  GET    /api/v1/knowledge-base/documents
  GET    /api/v1/knowledge-base/documents/{id}
  PUT    /api/v1/knowledge-base/documents/{id}
  DELETE /api/v1/knowledge-base/documents/{id}

Asserts the DELETE physically removes the stored file from disk and its linked
upload row from MongoDB.
"""

import os
import shutil
import sys

os.environ["MONGO_DB"] = "ai_commerce_e2e_test"
os.environ["JWT_SECRET"] = "test-jwt-secret-shared-0123456789abcdef"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-shared-0123456789abcdef"

UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "e2e_uploads"))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from tests.conftest import admin_headers  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}{(' - ' + detail) if detail and not condition else ''}")
    if not condition:
        FAILURES.append(name)


def main() -> int:
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.environ["UPLOAD_LOCAL_PATH"] = UPLOADS_DIR
    # knowledge_settings reads at import time; re-point the module default.
    from app.core.knowledge_settings import knowledge_settings

    knowledge_settings.upload_local_path = UPLOADS_DIR

    head = admin_headers(store_id="22222222-2222-2222-2222-222222222222")
    with TestClient(app) as client:
        src = os.path.join(UPLOADS_DIR, "faq-source.txt")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("What are your return policies?\nReturns accepted within 30 days.\n")

        r = client.post(
            "/api/v1/knowledge-base/upload",
            params={"knowledge_scope": "general"},
            headers=head,
            files={"file": ("faq.txt", src, "text/plain")},
        )
        check("upload -> 201", r.status_code == 201, f"got {r.status_code}: {r.text}")
        if r.status_code != 201:
            return 1
        body = r.json()
        upload_id = body["id"]
        document_id = body.get("document_id")
        check("upload returns document_id", bool(document_id), body)

        r = client.get("/api/v1/knowledge-base/documents", headers=head)
        check("list documents -> 200", r.status_code == 200)
        docs = r.json()["items"] if r.status_code == 200 else []
        check("document present in list", any(d["id"] == document_id for d in docs))

        r = client.get(f"/api/v1/knowledge-base/documents/{document_id}", headers=head)
        check("get document -> 200", r.status_code == 200, r.text)
        stored_title = r.json()["title"] if r.status_code == 200 else ""
        check("document title is original filename", stored_title == "faq.txt", stored_title)

        r = client.put(
            f"/api/v1/knowledge-base/documents/{document_id}",
            headers=head,
            json={
                "title": "FAQ - Updated",
                "description": "Merchant-curated FAQ policies for customer support.",
                "status": "active",
                "language": "en",
            },
        )
        check("update document -> 200", r.status_code == 200, r.text)
        updated = r.json() if r.status_code == 200 else {}
        check("updated title persisted", updated.get("title") == "FAQ - Updated", str(updated))

        stored_file = os.path.join(UPLOADS_DIR, body["stored_filename"])
        check("stored file exists before delete", os.path.isfile(stored_file), stored_file)

        r = client.delete(f"/api/v1/knowledge-base/documents/{document_id}", headers=head)
        check("delete document -> 200", r.status_code == 200, r.text)
        check("delete returns success=true", r.status_code == 200 and r.json().get("success"), r.text)
        check("stored file removed from disk", not os.path.isfile(stored_file), stored_file)

        from bson import ObjectId
        from pymongo import MongoClient as SyncMongoClient

        db_name = "ai_commerce_e2e_test"
        with SyncMongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000) as sdb:
            upload_still_exists = sdb[db_name]["knowledge_uploads"].find_one(
                {"_id": ObjectId(upload_id)}
            )
            doc_still_exists = sdb[db_name]["knowledge_documents"].find_one(
                {"_id": ObjectId(document_id)}
            )
        check("linked upload row removed", upload_still_exists is None)
        check("document row removed", doc_still_exists is None)

        r = client.get(f"/api/v1/knowledge-base/documents/{document_id}", headers=head)
        check("get document after delete -> 404", r.status_code == 404, r.text)

        if FAILURES:
            print(f"\n{len(FAILURES)} FAILURES")
            return 1
        print("\nALL E2E CHECKS PASSED")
        return 0


if __name__ == "__main__":
    import atexit

    def _cleanup() -> None:
        try:
            from pymongo import MongoClient as SyncMongoClient

            with SyncMongoClient(
                "mongodb://localhost:27017/", serverSelectionTimeoutMS=3000
            ) as sdb:
                sdb.drop_database("ai_commerce_e2e_test")
        except Exception:
            pass
        shutil.rmtree(UPLOADS_DIR, ignore_errors=True)

    atexit.register(_cleanup)
    sys.exit(main())
