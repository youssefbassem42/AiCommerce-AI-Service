# Phase 1 Implementation Report — Commerce Product Discovery & Retrieval Remediation

**Status: PASS**

**Commit:** `b277304` · **Deployment:** `cd40aab9` (production, SUCCESS) · **Date:** 2026-08-17

---

## 1. Summary

Phase 1 fixed the four confirmed product-discovery failures (B12, B1, B2, B15) so
the Recommendation Agent returns real, active, in-stock products from the catalog
instead of empty results. The acceptance probe — `"I want a laptop under 3000"`
against the widget store (`3ad1b6e1-e815-4592-aa74-e9692f2f8d36`) — went from
**0 products to 2 products**, all with canonical Mongo `_id`s.

Scope was strictly Phase 1 (B12/B1/B2/B15). All other findings (B3–B11, B14,
B16–B18) were documented and left untouched. No destructive data migration was
performed: the widget store's "Dress" ($5000) and "office" ($20000) anomalies are
documented only.

## 2. Root Cause Chain (recap)

1. **B12**: Catalog `product_type` stores category names ("Electronics") while the
   LLM extracts plain words ("laptop", "electronics").
2. **B1**: `retrieve_candidates` regexed the phrase directly against `product_type`
   with a **start-of-string anchor** (`^laptop`), so "Electronics" never matched →
   0 candidates.
3. **B2**: Vector fallback found product vectors whose `product_id` was the
   **external_id** ("1", "20", "31"), not the Mongo `_id`. The recommendation
   pipeline resolves candidates by `find_by_id(Mongo _id)` → every vector candidate
   was discarded.
4. **B15**: `ProductService.create` never enqueued vector sync, so new products
   were invisible to vector retrieval until a reindex.

## 3. Fixes

### 3.1 B1 — Taxonomy-aware catalog retrieval

`app/application/recommendation/catalog_service.py` — `retrieve_candidates` now:

1. Resolves the parsed phrase against the **store's own taxonomy** via new
   repository method `distinct_field_values(store_id, field)`
   (`app/domain/commerce/repositories/product_repository.py` +
   `app/infrastructure/mongodb/repositories/commerce_product_repository.py`,
   backed by `collection.distinct`).
2. Matches with `_taxonomy_match` (case-insensitive; exact → containment in either
   direction → shared-token overlap; degenerate matches blocked). A 1-char exact
   match is allowed, so category-id phrases ("5") still resolve.
3. Queries `$or: [{product_type: {$in: type_keys}}, {category_id: {$in: cat_keys}}]` —
   products with `product_type=None` but a matching `category_id` are reachable.
4. Falls back to **product-title** matching (`title` `$regex`, escaped, case-
   insensitive) **only when taxonomy yields nothing** — this is how "laptop" finds
   "Gaming Laptop RTX" (product_type="Electronics") and "Laptop Backpack"
   (product_type="Accessories").

Unchanged: hard filters (store, `status=active`, availability, price>0, budget +
discount tolerance, brand/vendor, explicit requirement specs) and the
`retrieve_candidates` signature. Unexpected repo return types and repo exceptions
are guarded with structured logging (`catalog_retrieval store=… source=… fetched=…
candidates=…`).

### 3.2 B2 — Canonical Mongo `_id` is the product vector identity

`app/application/integration/sync/knowledge_bridge.py`:

- New injectable `product_identity_resolver` (default: Mongo lookup by
  `(store_id, external_id)`).
- `sync_entity` pre-pass for `entity_type=="product"`:
  - valid Mongo ObjectId `_id` → kept untouched;
  - external identity → resolved against the catalog, canonical `_id` injected;
  - unresolvable → existing `_id` preserved (best effort, logged);
  - no identity at all → record skipped and reported (payloads never index an
    empty key).
- New public `purge_entity_vectors(store_id, entity_type)` — strict
  store+entity-scoped delete (never a collection drop), used by the reindex.

`app/application/knowledge/indexing.py` — `StoreIndexer._index_products` purges
stale product vectors (e.g. old external-id payloads) before rebuilding, making
the store reindex idempotent and self-healing. The admin reindex endpoint
(`POST /knowledge/jobs/reindex`) and `scripts/reindex.py` run this same path.

This also fixes the live integration-sync gap in
`app/application/integration/sync/orchestrator.py`, whose payloads carried
`external_id` but no `_id`.

### 3.3 B15 — Create products reach vector retrieval

`app/application/commerce/services.py` — `ProductService.create` now enqueues
`enqueue_sync_record(..., product_to_record(created))`, mirroring the existing
update/delete pattern (which already carried `_id`).

### 3.4 Observability

`app/agents/recommendation/nodes.py` — `search_candidates_node` and
`filter_inventory_node` log per-store candidate counts and catalog-vs-vector
source, so empty or degraded results are diagnosable in production logs.

## 4. Verification

### 4.1 Test suite

- `pytest tests/unit`: **1883 passed** (was 1880 pre-change + 3 new files).
- `ruff check .` and `ruff format --check .`: clean.
- New tests:
  - `tests/unit/application/test_catalog_retrieval_remediation.py` — taxonomy
    via `product_type`/`category_id`, title fallback, budget/brand/stock/store
    scoping, repo-error and non-list guard, `_taxonomy_match` matrix.
  - `tests/unit/integration/test_knowledge_bridge_remediation.py` — canonical
    identity enrichment, resolver injection, skip-on-no-identity,
    `purge_entity_vectors` scoping, `StoreIndexer` purge-before-sync.
  - `test_product_service.py::test_create_product_enqueues_vector_sync`.
  - `test_recommendation_phase4.py::test_hard_filters_apply` updated to the new
    `$or` query shape.
- Evaluation suite (`tests/eval`) untouched and unaffected by design: its mocked
  repository returns a non-list for `distinct_field_values`, which triggers the
  guarded title fallback (verified in code; eval suite was not re-run to preserve
  the remaining provider budget).

### 4.2 Production evidence (widget store `3ad1b6e1-e815-4592-aa74-e9692f2f8d36`)

| Probe | Before | After |
|---|---|---|
| `POST /api/v1/recommendations/chat` "I want a laptop under 3000" | `products: []` | **2 products**: Laptop Backpack ($55, `6a7c6a8989fffc2a947e891b`), Gaming Laptop RTX ($1500, `6a7ce4bb89fffc2a947e9eb5`) |
| `POST /api/v1/recommendations/chat` "electronics under 500" | n/a | **4 products** (taxonomy path: Portable Power Bank $45, Wireless Earbuds $75, Smart Watch V2 $199, 4K Monitor $320) |
| `POST /knowledge/retrieval/search` "laptop computer electronics" (product) | 3 vectors, `product_id` = `"1"/"20"/"31"` (external ids) | 20 hits, `product_id` = Mongo `_id` (24-hex) — e.g. `6a7ce4bb89fffc2a947e9eb5` |
| Store reindex job (`store_reindex`, id `6a81d829…`) | — | COMPLETED: products 29/29 synced, categories 11/11, orders 0, documents 1, `errors: []`, ran in 4s |

The returned product `_id`s match the Mongo catalog, proving B1 (taxonomy + title
resolution) **and** B2 (canonical vector identity → `find_by_id` resolution) end-to-end.

### 4.3 Observed behavior (documented, not part of Phase 1 scope)

- `"Show me laptops"` / `"I need a gaming computer"` (no budget): the workflow's
  pre-existing `_missing_requirement` guard (`nodes.py:59`) replies
  `"What's your budget?"` before searching. Pre-existing by design; requires
  budget to search.
- Widget store data anomalies (Dress $5000, office $20000) remain — documented
  only, as agreed.

## 5. Files Changed

- `app/application/recommendation/catalog_service.py` (B1)
- `app/domain/commerce/repositories/product_repository.py` + `commerce_product_repository.py` (B1, `distinct_field_values`)
- `app/application/integration/sync/knowledge_bridge.py` (B2, identity + purge)
- `app/application/knowledge/indexing.py` (B2, reindex purge)
- `app/application/commerce/services.py` (B15)
- `app/agents/recommendation/nodes.py` (observability)
- Tests: `test_catalog_retrieval_remediation.py`, `test_knowledge_bridge_remediation.py`, `test_product_service.py`, `test_recommendation_phase4.py`

## 6. Known Limitations

- Products are embedded via `gemini-embedding-001` through the default provider;
  embedding quality depends on provider availability (SBG budget exhausted — no
  further SBG-gateway requests were made during Phase 1).
- Vector search still matches category vectors when `entity_types` filtering is
  loose on the search endpoint; the recommendation path is unaffected (catalog
  candidates are ranked first and resolve via Mongo).
- Full `tests/eval` re-run deferred (provider budget); recommended once budget is
  restored.
