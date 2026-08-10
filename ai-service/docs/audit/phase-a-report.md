# Phase A Report — Baseline & Inventory

## 1. Status

**PASS WITH WARNINGS** — baseline captured; no code behavior changed. No test failures at baseline. Three warning-class findings documented (client-controlled tenant/AI fields on internal routes; `JWT_REQUIRED` default; unmounted legacy knowledge router).

## 2. What Was Audited

- Live OpenAPI schema generated from the running application (`app.main`), 85 paths / 105 operations / 134 schemas.
- All 18 mounted routers (`app/api/*`), their auth dependencies and tenant sources.
- Global middleware stack: `AuthMiddleware`, `RateLimitMiddleware`, `AuditMiddleware`, `AITracingMiddleware`, `WidgetCorsMiddleware`, `CORSMiddleware`.
- Request models carrying tenant or AI-execution fields (A4).
- MongoDB repository inventory (22 repositories) and the legacy knowledge router mount status.
- Full test suite status (A5).

## 3. What Was Changed

| File | Change |
|---|---|
| `docs/api/openapi-baseline.json` | A1 — OpenAPI schema generated verbatim from the live app (85 paths, 134 schemas) |
| `docs/api/endpoint-ownership-matrix.md` | A2 — 105-operation ownership matrix (consumer/auth/tenant/request/response/side effects/collections/risk) |
| `docs/audit/phase-a-report.md` | This report |

No application code, configuration, or tests were modified.

## 4. What Was NOT Changed

Preserved: all endpoints and contracts, RAG engine, LLM provider abstraction, MongoDB/vector stack, widget implementation, authentication contract, middleware order, test suite (1364 tests untouched), database schema and indexes.

## 5. Tests Executed

Baseline run (`pytest tests/`): **1364 passed, 0 failed, 0 skipped, 0 errors** (58s, 111 warnings — all third-party deprecation noise).

| ID | Test | Result | Evidence |
|---|---|---|---|
| A5-01 | Full unit suite | PASS | 1364 passed |
| A5-02 | Widget unit tests | PASS | 12 passed |
| A5-03 | Conversation/tenant scoping tests | PASS | included in suite |

Coverage tooling available (`coverage.py 7.15.2`) but no configured coverage gate; not run as part of baseline.

## 6. Failures Found

None in the test suite. Audit findings (see §12 for risks):

- **F-01 (P3)**: `app/api/knowledge/router.py` (legacy) defines 19 unauthenticated routes (`/documents|chunks|summaries|uploads` CRUD) but is **not mounted** in `app/main.py` — dead code. No live exposure.
- **F-02 (P3)**: `.env` uses a development `JWT_SECRET` placeholder; `JWT_REQUIRED` is absent from both `.env` and `.env.example` (defaults to `false`).

## 7. Fixes Applied

None — Phase A explicitly prohibits behavior changes. Baseline artifacts only.

## 8. Security Impact

Unchanged (no code changes). The baseline now documents the exact trust model: all `/api/v1/*` SaaS routes are bearer-JWT bound; RAG/recommendation routes accept client tenant fields when anonymous; widget routes are key/JWT bound.

## 9. Production Impact

None. Zero application changes.

## 10. API Impact

- Added endpoints: none
- Modified endpoints: none
- Deprecated endpoints: none
- Unchanged endpoints: all 105
- Breaking changes: none

## 11. Database Impact

No schema changes, no indexes, no migrations, no data migrations.

## 12. Remaining Risks

| ID | Finding | Severity | Evidence |
|---|---|---|---|
| R-01 | `JWT_REQUIRED=false` is the effective default → anonymous mode for `/rag/*` (client-supplied `store_id`/`organization_id` honored when no token) | P2 | `app/core/auth_settings.py:16`; `app/api/rag/router.py:22-25`; `.env` |
| R-02 | `POST /api/v1/recommendations/*` falls back to client-supplied `store_id` when tenant context absent | P2 | `app/api/recommendation/router.py:42,82` |
| R-03 | `WidgetChatRequestSchema` exposes AI execution controls (`model`, `temperature`, `max_tokens`, `top_k`, `score_threshold`, `use_hybrid`, `use_mmr`, `rerank`, `knowledge_scope`) to an untrusted browser client → uncontrolled cost/behavior | P2 | `app/api/widget/schemas.py` (kept for compatibility per plan §1.7) |
| R-04 | `/knowledge/retrieval/search` trusts request-supplied `store_id`/`organization_id` (authenticated user only) | P2 | `app/api/knowledge/retrieval_router.py` |
| R-05 | Legacy unmounted knowledge router is dead code (confusion/rot risk) | P3 | `app/main.py:17-20` imports; unused module |
| R-06 | `store_id` is used as the canonical tenant boundary, with `organization_id` present alongside in several DTOs — org/store consistency is untested end-to-end | P2 | to be validated in Phase C |
| R-07 | Runtime logs carry no `X-Request-ID`; correlation is partial (`correlation_id` inside chat service only) | P2 | Phase B scope |
| R-08 | No per-endpoint / per-widget-session rate limits (single global per-IP limiter) | P2 | Phase D scope |
| R-09 | `X-Widget-Key` header is not rate-limited by key; bootstrap is per-IP only | P2 | Phase D scope |

## 13. Required Action

| Issue | Severity | Action | Owner | Blocking? |
|---|---|---|---|---|
| R-01/R-02/R-04 | P2 | Phase C tenant-isolation tests; decide enforcement (server-derived tenant) via compatibility layer, not immediate removal of fields | AI service | Phase C gate |
| R-03 | P2 | Phase E: widget V2 request + server policy; keep compatibility adapter | AI service | Phase E gate |
| R-07 | P2 | Phase B: X-Request-ID correlation | AI service | Phase B gate |
| R-08/R-09 | P2 | Phase D: endpoint-aware limits | AI service | Phase D gate |
| R-05 | P3 | Remove or mount legacy router (requires contract decision) | AI service | No (backlog) |
| R-06 | P2 | Phase C tenant isolation matrix | AI service | Phase C gate |

## 14. Exit Gate

**PASS WITH WARNINGS**

- [x] OpenAPI baseline created
- [x] Endpoint ownership matrix created (105/105 classified, 0 UNCLASSIFIED)
- [x] API contract audit (A3) completed
- [x] Request-model audit (A4) completed — 23 request schemas carry tenant/AI-control fields, `RAGChatRequestSchema` is the fattest
- [x] Baseline test run recorded (1364 pass / 0 fail / 0 skip)
- [x] No existing endpoint intentionally removed
- [x] No production DB migration with destructive changes
- [ ] NOT in scope for A: internal service auth verification (Phase C), vector metadata audit (Phase C), prompt/config isolation (Phase C)

Proceeding to **Phase B (Request Correlation & Observability)**.