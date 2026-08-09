# AiCommerce AI-Service — Broken Parts Report (live-verified)

Generated from a full debug session: module imports, 1341-test suite, live server boot against the real Mongo Atlas DB (`ai_commerce`), minted contract-matching JWT, smoke test of every registered route, real sync against `mult-vendor-ecommerce.runasp.net`, provider/Qdrant/model-registry checks, event-bus scan and frontend path cross-check.

Status of the four audit areas:
- **sr-only**: `✅ OK` = verified working; `🔴 BROKEN` = verified failing; `🟠` = broken wiring or incomplete.

---

## 1. VERIFIED WORKING (do not touch)

| Area | Evidence |
|---|---|
| Module compile + import of every package under `app/` | `compileall` + full import walk: 0 failures |
| Automated tests | `1341 passed, 0 failed` (unit + integration + e2e) |
| JWT auth contract | HS256, `iss/aud=AI-Sales-Agent`, GUID `sub`, `store_id`/`org_id`, `security_stamp` (minted token → 200) |
| Real store sync pipeline | `POST /agent-sync` with `openapi-1.yaml` spec → 200; `POST /connections/{id}/sync` → status `complete`, products landed in Mongo |
| Celery | 16 tasks registered; beat (4 schedules); routes cover `default,ingestion,embedding,summarization,scheduler,cleanup`; worker in prod consumes all queues |
| Model registry | 30 models, all requested names resolve (`gpt-4o-mini`, `deepseek-chat`, `gemini-2.0-flash`, `text-embedding-3-small`, …) |
| Knowledge upload (multipart) | 201, file stored + hashed |
| Tickets | list/metrics/resolution/create → 200/201 |
| RAG search (empty vector store) | 200 structured empty result (graceful) |

---

## 🔴 1. Catalog / orders / inventory / customers READ 500 (the "products 0" bug)

### What breaks
`GET /api/v1/commerce/products` → **500** once any synced product exists. Same for `orders`, `inventory`, `customers`. The product/order data IS in Mongo (56 products, 46 categories, 5 orders) but the repository can't deserialize it, so the UI (correctly calling this API) shows 0/error.

### Root cause A — broken `audit` default
- `app/infrastructure/mongodb/documents/base_document.py:26-29`
  ```python
  class AuditInfoModel(BaseModel):
      created_at: Any   # REQUIRED, no default
      updated_at: Any   # REQUIRED, no default
  ```
- `app/infrastructure/mongodb/documents/product_document.py:130` (same in `category_document.py`, `order_document.py`, `inventory_document.py`, `customer_document.py`)
  ```python
  audit: AuditInfoModel = Field(default_factory=AuditInfoModel)
  ```
  `AuditInfoModel()` raises `ValidationError` (created_at/updated_at missing) → every doc loaded WITHOUT the `audit` subdoc (i.e. every doc the sync writer wrote) fails at `ModelDocument.validate()`. Verified per collection: products FAIL, orders FAIL (5 errors), inventory FAIL, customers FAIL; categories/app-speakers OK (unluckily the one collection that happened to include audit).

### Root cause B — money shape mismatch
- Sync writer stores raw order money fields: `app/application/IntegrationSync/writers.py` (order writer): `"subtotal_price": data.get("subtotal"), "total_price": data.get("total)"`, `"line_items": data.get("line_items", [])`, `"currency": data.get("currency", "USD")`.
- The live store API returns money-shaped fields as `{"amount": …, "currency": "string"}` where `currency` is a **25-char string** (dev placeholder from the publisher). Read model `MoneyModel` (`product_document.py:13-19`) enforces `min_length=3, max_length=3` → 5 ValidationErrors on order read (`line_items[0].price.currency`, `total_price.currency`, …).

### Fix
1. Make `AuditInfoModel` safe:
   ```python
   created_at: datetime | None = None
   updated_at: datetime | None = None
   ```
   (or give `audit` a valid default factory that injects now timestamps).
2. Add normalize step in the sync writer: parse API money dicts `{amount?, currency?}` → `{"amount": float, "currency": "USD"[:3]}` before storing; skip non-3-letter currencies.
3. Add a migration/on-class normalize: `MoneyModel` to accept `currency` with `len>3` via validator converting ISO→code (or trust the writer fix + one-time repair script).

### Acceptance test
`GET /api/v1/commerce/products` returns 200 with the 29 promoted products; `GET /api/v1/commerce/orders` returns 200 with line items; pytest suite still 1341 passed.

---

## 🔴 BROKEN 2 — LLM front-door: no provider actually calls the LLM

### What breaks
`POST /api/v1/ai/chat` → `AIException … 402 (openrouter)`. `/api/v1/ai/embeddings` → 401 "API key not valid" (mock-key). `/ai/chat/structured`, `/ai/chat/stream`, tool-calling, ticket sentiment, bundles, recommendations silently degrade / 500.

### Live provider health status
| Provider | Health | Failure |
|---|---|---|
| openrouter | healthy | `402 Payment Required — requires more credits` on any real call |
| openai | unhealthy | `401 Incorrect API key provided: mock-key` |
| gemini | unhealthy | `400 INVALID_ARGUMENT – API key not valid` |
| claude | unhealthy | `Could not resolve authentication method` (no api_key passed) |
| mistral | unhealthy | `Illegal header value b'Bearer '` (empty token header bug) |
| deepseek | INSTANTIATE-ERR | `Missing credentials …` (SDK called with wrong param) |
| azure | unhealthy | connection timeout |
| ollama | healthy (local only) | — |
| mock | healthy | returns canned text — used as fallback everywhere |

### Root causes
- `app/infrastructure/providers/openai_provider.py:35` (+ gemini/openrouter/azure): `api_key = … or "mock-key"` — default key fallback that silently poisons prod.
- `app/infrastructure/providers/mistral_provider.py`: builds `Authorization: Bearer {key}` with empty key → `b'Bearer '` header, rejected.
- `app/infrastructure/providers/deepseek_provider.py`: constructs the client with the openai SDK using a wrong kwarg (`api_key` omitted → KeyError/`api key` requirement) — actually returns `Missing credentials` when None; needs explicit param name / base_url.
- Embedding provider chain in `get_embedding_provider` (`app/api/knowledge/retrieval_dependencies.py`) tries gemini → openai → mock, but exceptions surface from the CALL, not instantiation → no runtime fallback.

### Fix
1. Remove the `or "mock-key"` defaults (raise explicit config error instead).
2. Fix mistral header (guard empty key).
3. Fix deepseek SDK instantiation (param name + base_url `https://api.deepseek.com`).
4. Make provider factory / `get_embedding_provider` implement per-call fallback (try each provider in list, return first working chat/embed result).
5. Set real keys in Railway env: `OPENROUTER_API_KEY` (has credit issue — needs top-up of $), `GEMINI_API_KEY`, `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` (pick one primary). Provide `DEFAULT_PROVIDER` accordingly.

### Fix R
`POST /api/v1/ai/chat` returns assistant text (200); `/api/v1/ai/embeddings` returns 1536-dim embedding with a real provider.

---

## 🔴 BROKEN 3. Qdrant never has indexes (RAG/recommendation silent-empty)

### What breaks
- Local Qdrant: `health_check=True` but `collections: []` — **never created**.
- Prod: Qdrant env vars (`QDRANT_HOST/PORT`) exist on Railway but **no Qdrant service exists** in the project → vector ops `Connection refused`, `Vector store unavailable … skipping` warnings on every sync.

### Impact
Knowledge search → `0 results`; recommendations/bundles empty; `knowledge.sync_vectors`/`kb.sync_vector_db` jobs can never complete; embedding pipeline dead in prod.

### Fix
1. Provision Qdrant — either a Railway image service (qdrant/qdrant) or Cloud (cluster URL + API key).
2. Point `QDRANT_HOST`, `QDRANT_PORT` (+ secrets KEY/ path) to it.
3. Re-run the knowledge indexing flow to create the default collection with embedding vector size (gemini-embedding-001 ⇒ 768-dims per config) and nreferences.

### Fix R
`/api/v1/knowledge-base/search` returns at least one result for a queried content; health shows collections non-empty.

---

## 🟠 BROKEN 4. Route wiring — stray paths + dead router

| Broken | File | Currently | Should be |
|---|---|---|---|
| Chat | `app/api/chat/router.py:11` | `/chat` | `/api/v1/chat` |
| RAG | `app/api/rag/router.py:14` | `/rag/chat` | `/api/v1/rag/chat`? (matches rest) |
| Jobs | `app/api/knowledge/job_router.py:23` | `/knowledge/jobs/*` | `/api/v1/knowledge-base/jobs/*` |
| Retrieval | `app/api/knowledge/retrieval_router.py:13` | `/knowledge/retrieval/search` | `/api/v1/knowledge-base/retrieval/search` |
| Dead router | `app/api/knowledge/router.py` | not included in main | include or remove (has CRUD for documents/chunks/summaries/uploads) |

Also `main.py:96-112` misses `knowledge_router` import altogether.

### Fix
Add consistent `/api/v1` prefixes; import knowledge CRUD router in `app/main.py` or delete file; deduplicate with unified router (unified already covers documents/jobs/upload).

---

## 🟠 BROKEN 5. Agents & DTO wiring gaps

- **PromptClient not wired**: `grep PromptClient` finds only `app/infrastructure/prompts/client.py` — admin-visible prompt editing (`/api/v1/admin/prompts`) has no effect on any agent.
- **Domain events wholly unused**: `add_domain_event` has zero call sites; bus has zero subscriptions; no mediator instantiated anywhere. The events/event-sourcing layer is dead weight (or fake).
- Agents `BundleSuggestionAgent`, `RecommendationAgent`, `CoordinatorAgent` require injected repos+LLM (normal), but DI (`app/api/rag/dependencies.py`) wires only the subset used by RAG; other entry points (`recommendations/bundle-suggestion`, `ai/chat/tools`) hit constructor errors.
- Real run confirmed: `search_spec_vectors` expects retriever returning `.results`; when the vector store returns raw list → `'list' object has no attribute 'results'` in `nodes.py:48`.

### Fix
1. Inject `PromptClient` into each agent call site (bundle, recommendation, integration, coordinator, escalation, sales, support) with hardcoded fallback.
2. Either connect the event bus (raise OrderPlaced on order create → analytics update) or remove the dead subsystem.
3. NORMALIZE the retriever contract: `RetrieverService.search` always returns `UnifiedRetrievalResult`; handle list responses in tools.

---

## 🟡 BROKEN 6. API-surface consistency (field names, roles, sec)

- `Commerce` schemas mix `organization_id` (ProductCreate) vs `org_id` (Category/Order/Inventory) — documented/api/json mismatch, 422 for frontends sending uniform field (`app/api/commerce/schemas.py`).
- `require_admin_role` duplicated with OPPOSITE semantics: `app/api/analytics/dependencies.py` REJECTs `super_admin` for store analytics; `app/api/auth/dependencies.py` treats it as allowed. Unify with one policy.
- **`JWT_SECRET` is the documented production placeholder**: dev `.env` value `CHANGE_ME_…` validates & passes in prod (token minted with it → 200). Any .NET backend uses the same default ⇒ remote token forgery. Replace with strong random + document rotation.
- Pydantic V2 deprecations: `Field(…, index=True)` in several doc models (warnings only now, breaks at V3).
- Frontend verified to call the REAL canonical paths (`/ai/chat`, `/knowledge-base/jobs/{id}`) — the stray/root routes are unused surfaces, no frontend change needed for those.

---

## Repair order (each step ends with: pytest + live smoke)

| # | Task | Verify with |
|---|---|---|
| 1 | Fix `audit`/money read-back (BROKEN-1) | `GET /commerce/products` 200 + orders 200 |
| 2 | LLM providers fixes + real keys (BROKEN-2) | `/ai/chat` 200 real, `/ai/embeddings` real vector |
| 3 | Provision Qdrant + index (BROKEN-3) | knowledge search returns hits |
| 4 | Route prefixes + dead router (BROKEN-4) | openapi.json paths all `/api/v1/*`; full pytest |
| 5 | PromptClient wiring + event bus + retriever contract (BROKEN-5) | admin prompt change affects agent output |
| 6 | Field-name unification (`org_id` everywhere), admin-role policy, JWT_SECRET rotation (BROKEN-6) | live 200s; forgery-probe fails |