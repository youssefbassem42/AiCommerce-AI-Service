# Knowledge Tenant Data Audit — AiCommerce AI Service

Date: 2026-08-13
Scope: production `ai_commerce` Mongo + Qdrant (project `charming-comfort`)
Reference store under test: `3ad1b6e1-e815-4592-aa74-e9692f2f8d36` (widget `wid_a9e1d0d4376d4249`, organization `af54ad71-ffbe-4968-bea0-92444935ea6a`)

## 1. Collections / corpus inventory

| Qdrant collection | Points | Composition |
|---|---|---|
| `kb_3ad1b6e1-e815-4592-aa74-e9692f2f8d36` | 97 | 57 `knowledge_document` (salla_file.pdf), 29 `integration_sync` products, 11 `integration_sync` categories |
| `kb_8a1781f9-bca3-452a-879a-5b01a3268fd4` | — | orphan store (no organization anywhere) |
| `kb_8a3cba3d-ba11-40a9-9d38-326bf3e9d8ea` | — | orphan store |
| `kb_8e57e6cc-8c97-47f5-9e41-35c4d8a6a648` | — | orphan store |

No global/default collection exists; per-store collection isolation is intact.

## 2. Findings

### F1 — Legacy document chunks were not tenant-scoped (FIXED)
- All 57 chunks of document `6a7d7930603db8b6680ef929` (salla_file.pdf) were written by an older pipeline that stamped `store_id`/`organization_id` on neither the Mongo chunk docs nor the Qdrant payloads.
- Impact: the org-scoped retrieval filter (`organization_id AND store_id AND document_status=active`) matched only the 40 product points, so the store's own KB was invisible to chat retrieval. Answers fell back to the business summary (v1) or refusal.
- No cross-tenant leakage was observed: store_id was present on every point, so no store could read another store's chunks.

### F2 — Two chunk payload schemas coexisted (FIXED)
- Legacy/demo chunks: top-level `store_id`/`organization_id` fields, metadata `[doc_title]`.
- Current `ChunkingService` chunks: tenant fields inside `metadata`.
- `sync_vectors_task` payload fallback already reads `metadata.get("store_id"/"organization_id")`, so the Mongo backfill alone makes future re-syncs correct.

### F3 — Product vectors lacked structured price/currency/specs (FIXED)
- `CommerceKnowledgeBridge._build_payload` only wrote `product_id`/`product_title` for products; price existed only inside the free-text content.
- `search_spec_vectors` therefore returned `ScoredProduct(price=0, currency="USD")` for non-budget queries.

### F4 — Store→organization mapping is incomplete for legacy stores (UNRESOLVED, fail-closed)
- `entities` / `widget_installations` map org only for the widget store. KB stores `8a1781f9-…`, `8a3cba3d-…`, `8e57e6cc-…` (and document stores `19127128-…`, `3760c626-…`) have no resolvable organization anywhere in the system.
- Decision: leave these collections untouched (fail-closed — invisible to org-scoped retrieval). Re-syncing these stores via their Salla integrations will stamp orgs. No orgs were invented.

## 3. Remediation executed (production)

1. **Code (repo, to be deployed)**
   - `chunking_service.py`: `chunk_document(..., organization_id=None)` threads the org through `_delete_and_recreate`/`_build_chunks`; metadata now includes `organization_id`.
   - `coordinator.py`: `_chunk_document` passes `tenant.organization_id`.
   - `workers/ingestion/tasks.py`: `chunk_document_task` and `generate_chunks_task` accept/forward `organization_id`; `_dispatch_vector_chain(store_id, chunks, organization_id=None)` no longer hardcodes `None`; `_resolve_store_organization_id()` best-effort resolution from the `entities` collection for call sites without org (indexing, upload reprocess).
   - API routers pass org where available (`unified_router` ×2, `job_router`).
   - `knowledge_bridge._build_payload`: product payloads now include `price` (float), `currency`, `image_url`, `product_url` (handle), and `specs` (sku, vendor, product_type, inventory_quantity, compare_at_price, category_id, tags).
   - `records.product_to_record`: propagates `currency` from variant/flat Money.
   - `recommendation/tools.search_spec_vectors`: hydrates `ScoredProduct` (price/currency/image_url/product_url/specs) from the vector payload.

2. **Data (applied directly to production)**
   - Mongo backfill: `knowledge_chunks.update_many({document_id: 6a7d7930603db8b6680ef929}, {$set: {metadata.store_id, metadata.organization_id}})` → 57 docs.
   - Qdrant re-sync: 57 doc points deleted + re-embedded + re-upserted with org in payload (mirrors `sync_vectors_task`).
   - Product re-sync: 29 products re-synced via `CommerceKnowledgeBridge.sync_entity` with enriched payloads (stale product points deleted).

## 4. Verification (post-fix, production Qdrant)

| Filter | Before | After |
|---|---|---|
| store only | 97 | 97 |
| ORG + STORE + document_status=active | 40 | **97** |
| doc chunks without organization_id | 57 | **0** |
| product points with price | 0 | **29** |
| product points with currency | 0 | **29** |

## 5. Residual risks / follow-ups
- Orphan KB collections (F4) remain invisible by design — re-sync via integration to reclaim.
- New ingestion paths now stamp orgs at the source; audit any future collections with the same check.
- `wgt_`→`wi_` naming was corrected in widget docs (cosmetic).
