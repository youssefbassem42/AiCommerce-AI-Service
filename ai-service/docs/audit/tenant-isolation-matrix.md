# Tenant Isolation Matrix — Enforcement & Test Coverage

**Owner:** AI service · **Phase C** · **Status: COVERED (C1–C10)**

Doctrine: the tenant identity is **server-derived from validated JWT claims**.
A client-supplied identifier that conflicts with the claim is a manipulation
attempt → **denied (403)**, never silently re-scoped. A request without the
required claim → **denied (403)**. Only the documented anonymous modes
(`JWT_REQUIRED=false`; widget/agent internal callers) may supply tenant fields,
and they never bypass an authenticated path.

| ID | Surface | Enforcement point | Claim source | Client `store_id` attempt | Outcome | Tests |
|---|---|---|---|---|---|---|
| C1 | Vector retrieval `POST /knowledge/retrieval/search` | `retrieval_router._resolve_filters` (deny) + `RetrieverService._enforce_tenant_scope` (override) + `RetrieverService._build_filter_conditions` (filters) | `request.state.store_id/org_id` (JWT) | mismatched → 403, search never runs | cross-store vectors unreachable | `test_tenant_isolation.py` search suite + `test_retrieval_router` |
| C2 | Knowledge CRUD (list/get/create/update/delete) | `get_current_store_id` dependency (403 without claim); service methods take `owner_store_id`/`store_id` from claims | JWT `store_id` | N/A (no client tenant field) | cross-store document access denied | `test_unified_router.py` |
| C3 | RAG chat `POST /api/v1/rag/chat` | `get_tenant_context` (claims) → `TenantContextResolver.from_claims`; retriever tenant-bound via `get_retriever_service` | JWT when present; payload when anonymous | authenticated: payload ignored (claims override) | foreign tenant context impossible when authenticated | `test_rag_router*`, `test_tenant_isolation.py` (retriever) |
| C4 | Recommendations `POST /api/v1/recommendations/*` | `tenant_context.store_id if tenant_context else payload.store_id`; retriever tenant-bound when claims exist | JWT when present | authenticated: claims win | foreign-store recommendations impossible when authenticated | `test_tenant_isolation.py` (retriever), recommendation API tests |
| C5 | Widget chat (public key) | widget JWT contract (Phase A guard, unchanged) | widget token | N/A | widget bound to its own tenant | `test_b06_widget_token_roundtrip_unchanged` |
| C6 | Ticket/conversation services | `store_id` carried through domain service args from claim-derived context | JWT | N/A | — | existing ticket/conversation suites |
| C7 | Business summaries | loaded by `store_id` from claim context (`RagOrchestrationService`) | JWT | N/A | — | `test_orchestration_service.py` |
| C8 | Version store (`knowledge_version`) | `RetrieverService._enforce_tenant_scope` overrides `knowledge_version` from tenant | JWT | version re-point → 403/override | cross-version read impossible | `test_tenant_version_isolates_chunks` |
| C9 | Chunk payload `store_id`/`knowledge_version` filter conditions | `_build_filter_conditions` emits `store_id`/`knowledge_version` eq filters; collection names namespace per store | JWT | N/A | filtered Qdrant queries always tenant-scoped | `test_caller_filters_are_overridden_by_tenant` |
| C10 | Analytics `GET /api/v1/analytics/sentiment-summary` | router claim binding + mismatch deny (Phase C fix) | JWT `store_id` | mismatched → 403, service never called | cross-store analytics impossible | `TestAnalyticsIsolation` |

## Failure modes documented (not silently hidden)

| Mode | Behaviour |
|---|---|
| Unbound retriever (no tenant, no filters) | logs warning — would query globally; only reachable via anonymous modes or misconfiguration |
| Token without `store_id` on a tenant-scoped route | 403 `ERR_NO_STORE` / `ERR_NO_ORG` |
| Client identifier conflicting with claim | 403 (denied as manipulation attempt) |
| Anonymous mode (`JWT_REQUIRED=false`) | RAG/recommendation accept client tenant (documented internal mode); retrieval search remains auth-required |

## Reference

- `app/api/knowledge/retrieval_router.py` — claim binding + mismatch deny
- `app/api/knowledge/retrieval_dependencies.py` — tenant-bound `RetrieverService` construction
- `app/application/knowledge/retrieval/service.py` — `_enforce_tenant_scope`, `_build_filter_conditions`
- `app/api/analytics/router.py` — claim binding + mismatch deny
- `app/api/auth/dependencies.py` — `get_current_store_id` / `get_current_organization_id`
- `tests/unit/security/test_tenant_isolation.py` — regression suite (12 tests)
