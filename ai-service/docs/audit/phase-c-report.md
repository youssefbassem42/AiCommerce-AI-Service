# Phase C Report — Tenant Isolation Enforcement

## 1. Status

**PASS** — after fixing one P0-class finding discovered during audit.

## 2. What Was Audited

- Retrieval path: `get_retriever_service` → `RetrieverService.search` → `_enforce_tenant_scope` → `_build_filter_conditions` (C1, C8, C9).
- Knowledge CRUD (C2): unified router binds every store-scoped operation to `get_current_store_id` (403 without claim).
- RAG (C3) and recommendations (C4): tenant resolution order `claims → payload`, retriever constructed from the same dependency.
- Analytics (C10): **found unbound** — `GET /api/v1/analytics/sentiment-summary` accepted a raw client `store_id` query param with no claim binding: any authenticated admin could read sentiment analytics for ANY store.
- Version scoping (C8/C9): `knowledge_version` included in tenant scope and filter conditions.
- Baseline: 1330 tests green before Phase C fixes (regression suite).

## 3. What Was Changed

| File | Change |
|---|---|
| `app/api/knowledge/retrieval_dependencies.py` | `get_retriever_service` now resolves `TenantContext` from `request.state` JWT claims and constructs a **tenant-bound** `RetrieverService`; no claims → unbound retriever reserved for the documented anonymous RAG mode |
| `app/api/knowledge/retrieval_router.py` | `_resolve_filters` is claims-only: missing claim → 403; client `store_id`/`organization_id` that conflicts with the claim → 403 (manipulation attempt); payload identifiers otherwise ignored |
| `app/api/analytics/router.py` | **P0 fix:** `/api/v1/analytics/sentiment-summary` now binds `get_current_store_id` (403 without claim) and denies a mismatched client `store_id` (403) |
| `tests/unit/security/test_tenant_isolation.py` | NEW — 12-test isolation regression suite (C1–C10 matrix) |
| `tests/unit/modules/knowledge/test_retrieval_router.py` | Updated legacy test that asserted the old insecure behavior (client-controlled tenant echoed into filters) to the claims-derived contract |
| `docs/audit/tenant-isolation-matrix.md` | NEW — enforcement matrix with claim source, attacker scenario, outcome, test IDs |

## 4. What Was NOT Changed

RAG and recommendation **anonymous mode** (`JWT_REQUIRED=false`): client tenant fields remain accepted there — documented internal mode, Phase A decision preserved. Widget JWT contract unchanged. All 105 API contracts preserved except the retrieval/analytics tenant semantics above (additive deny, no endpoint removal).

## 5. Tests Executed

| ID | Test | Result | Evidence |
|---|---|---|---|
| C1a | Tenant-bound retriever overrides caller store/org/version | PASS | `test_caller_filters_are_overridden_by_tenant` |
| C1b | Unbound retriever with no filters warns (failure mode documented) | PASS | `test_unbound_retriever_warns_on_global_scope` |
| C9 | Tenant version cannot be re-pointed; filter conditions tenant-only | PASS | `test_tenant_bound_version_isolates_chunks` |
| C1c | Search without store claim → 403, service not called | PASS | `test_search_without_store_claim_is_denied` |
| C1d | Mismatched payload store_id → 403, service not called | PASS | `test_search_mismatched_payload_store_is_denied` |
| C1e | Mismatched payload org_id → 403, service not called | PASS | `test_search_mismatched_payload_org_is_denied` |
| C1f | Search without payload identifiers uses claim store | PASS | `test_search_without_payload_uses_claim_store` |
| C1g | Search requires authentication | PASS | `test_search_requires_authentication` |
| C10a | Analytics mismatched store_id → 403, service not called | PASS | `test_mismatched_store_id_is_denied` |
| C10b | Analytics omitted store_id → claim store used | PASS | `test_omitted_store_id_uses_claim_store` |
| C10c | Analytics matching store_id allowed | PASS | `test_matching_store_id_is_allowed` |
| C10d | Analytics without store claim → 403 | PASS | `test_without_store_claim_is_denied` |
| — | Full regression suite | PASS | **1330 passed** |
| — | Ruff lint + format | PASS | clean on all touched files |

## 6. Failures Found During Phase

| Finding | Severity | Where | Fix |
|---|---|---|---|
| `POST /knowledge/retrieval/search` accepted client `store_id`/`organization_id` as fallback when claims absent, and echoed client identifiers into filter conditions when claims present (retriever `_enforce_tenant_scope` enforced claims only when a tenant was passed) | **P0** (cross-store vector read) | `retrieval_router.py`, `retrieval_dependencies.py` | Claims-only resolution; tenant-bound retriever; deny-on-mismatch |
| `GET /api/v1/analytics/sentiment-summary` took unbound client `store_id` | **P0** (cross-store analytics read) | `analytics/router.py` | Claim binding + deny-on-mismatch |

Both are closed: cross-store data access is now impossible on authenticated paths regardless of what the client sends.

## 7. API Impact

- `POST /knowledge/retrieval/search`: clients may still send `store_id`/`organization_id` (contract compatible) — now **ignored when matching** and **403 when conflicting**. Tokens without store/org claims can no longer search (previously fell back to client values).
- `GET /api/v1/analytics/sentiment-summary`: `store_id` query param now optional; when present must match the claim (403 otherwise). Without claim → 403.
- No endpoints added, removed, or deprecated.

## 8. Database / Vector Impact

None — no schema, index, or collection changes. Qdrant queries were already filtered per store; the fix ensures the filter values can only be claim-derived.

## 9. Phase A Risk Register — Status

| Risk | Phase A severity | Phase C outcome |
|---|---|---|
| R-01 retrieval search falls back to client store_id | P2 | **Closed** — claims-only + deny-on-mismatch (compat: storeless tokens → 403) |
| R-02 recommendations fall back to client store_id when tenant context absent | P2 | **Mitigated for authenticated mode** (claims win); anonymous mode fallback remains by design (documented internal mode) |
| R-06 org/store consistency untested | P2 | **Closed** — matrix + isolation tests assert both identifiers and version per tenant |
| R-04 (retrieval search client tenant fields) | P2 | **Closed** — see R-01 |

## 10. Remaining Risks

| ID | Issue | Severity |
|---|---|---|
| C-R1 | Anonymous mode (`JWT_REQUIRED=false`) trusts client tenant fields on RAG/recommendation — a misconfigured deployment would expose it; flag in deployment docs | P2 |
| C-R2 | `get_current_user`/claims path relies on `AuthMiddleware` ordering; a future middleware reorder could bypass claim population (guard test exists via middleware suite) | P3 |
| C-R3 | Runtime-log (`AIRuntimeLog`) writer still absent (carried from Phase B R1) | P2 |

## 11. Exit Gate

**PASS**

- [x] All isolation tests pass (12 new + full 1330 regression)
- [x] P0 findings fixed and covered by regression tests
- [x] Enforcement matrix documented (`docs/audit/tenant-isolation-matrix.md`)
- [x] Lint/format clean
- [x] No OpenAPI contract removal (tenant fields retained; behavior hardened)
