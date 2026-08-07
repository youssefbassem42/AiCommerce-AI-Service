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

os.environ["MONGO_URI"] = "mongodb://localhost:27017/"
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

    # Fresh baseline: clear any leftover data/files from interrupted runs.
    from pymongo import MongoClient as SyncMongoClient

    with SyncMongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000) as reset:
        reset.drop_database("ai_commerce_e2e_test")
    for leftover in os.listdir(UPLOADS_DIR):
        os.remove(os.path.join(UPLOADS_DIR, leftover))

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

        # --- Per-store dedup: re-upload of the exact same file is idempotent.
        r2 = client.post(
            "/api/v1/knowledge-base/upload",
            params={"knowledge_scope": "general"},
            headers=head,
            files={"file": ("faq.txt", src, "text/plain")},
        )
        check("same-file re-upload -> 200", r2.status_code == 200, f"got {r2.status_code}: {r2.text}")
        b2 = r2.json() if r2.status_code == 200 else {}
        check("same-file re-upload already_uploaded=true", b2.get("already_uploaded") is True, str(b2))
        check(
            "same-file re-upload returns same document id",
            b2.get("document_id") == document_id,
            str(b2),
        )

        # --- Different content -> version bump on the SAME document.
        src2 = os.path.join(UPLOADS_DIR, "faq-v2-source.txt")
        with open(src2, "w", encoding="utf-8") as fh:
            fh.write("Returns accepted within 30 days with original receipt.\nNo restocking fee.\n")

        r3 = client.post(
            "/api/v1/knowledge-base/upload",
            params={"knowledge_scope": "general"},
            headers=head,
            files={"file": ("faq.txt", src2, "text/plain")},
        )
        check("different-file upload -> 201", r3.status_code == 201, f"got {r3.status_code}: {r3.text}")
        b3 = r3.json() if r3.status_code == 201 else {}
        check("different-file already_uploaded=false", b3.get("already_uploaded") is False, str(b3))
        check(
            "different-file bumps same document",
            b3.get("document_id") == document_id,
            str(b3),
        )
        old_file = os.path.join(UPLOADS_DIR, body["stored_filename"])
        new_file = os.path.join(UPLOADS_DIR, b3.get("stored_filename", ""))
        check("previous file replaced on disk", not os.path.isfile(old_file), old_file)
        check("new file exists on disk", os.path.isfile(new_file), new_file)

        r = client.get(f"/api/v1/knowledge-base/documents/{document_id}", headers=head)
        ver = r.json().get("current_version") if r.status_code == 200 else 0
        check("document version bumped to 2", ver == 2, f"got current_version={ver}")

        # --- Tenant isolation: another store uploading the same file gets its OWN copy.
        head_b = admin_headers(store_id="99999999-9999-9999-9999-999999999999")
        rb = client.post(
            "/api/v1/knowledge-base/upload",
            params={"knowledge_scope": "general"},
            headers=head_b,
            files={"file": ("faq.txt", src, "text/plain")},
        )
        check("other-store same-file upload -> 201", rb.status_code == 201, f"got {rb.status_code}: {rb.text}")
        bb = rb.json() if rb.status_code == 201 else {}
        check("other-store not marked duplicate", bb.get("already_uploaded") is False, str(bb))
        check(
            "other-store gets isolated document",
            bb.get("document_id") is not None and bb.get("document_id") != document_id,
            str(bb),
        )

        stored_file = os.path.join(UPLOADS_DIR, b3["stored_filename"])
        check("stored file exists before delete", os.path.isfile(stored_file), stored_file)

        r = client.delete(f"/api/v1/knowledge-base/documents/{document_id}", headers=head)
        check("delete document -> 200", r.status_code == 200, r.text)
        check("delete returns success=true", r.status_code == 200 and r.json().get("success"), r.text)
        check("stored file removed from disk", not os.path.isfile(stored_file), stored_file)

        from bson import ObjectId
        from pymongo import MongoClient as SyncMongoClient

        db_name = "ai_commerce_e2e_test"
        with SyncMongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000) as sdb:
            latest_upload_still_exists = sdb[db_name]["knowledge_uploads"].find_one({"_id": ObjectId(b3["id"])})
            doc_still_exists = sdb[db_name]["knowledge_documents"].find_one({"_id": ObjectId(document_id)})
        check("latest upload row removed", latest_upload_still_exists is None)
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

            with SyncMongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000) as sdb:
                sdb.drop_database("ai_commerce_e2e_test")
        except Exception:
            pass
        shutil.rmtree(UPLOADS_DIR, ignore_errors=True)

    atexit.register(_cleanup)
    sys.exit(main())
