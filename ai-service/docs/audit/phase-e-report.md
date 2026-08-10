# Phase E Report — Widget AI-Execution Server Policy

## 1. Status

**PASS**

## 2. What Was Audited

- `WidgetChatRequestSchema` exposes AI execution controls to the untrusted browser client (Phase A R-03): `model`, `temperature` (0–2), `max_tokens` (≤8192), `top_k` (≤50), `score_threshold`, `use_hybrid`, `use_mmr`, `rerank`, `knowledge_scope`.
- `app/api/widget/router.py` `widget_chat` forwarded **every** control verbatim into `RAGRequest` → model selection (`request.model or DEFAULT_MODEL`) and `RetrievalConfig` (`top_k`, `score_threshold`, `use_hybrid`, `use_mmr`, `rerank`) — all driven by client input. A malicious client could select arbitrary provider models, max out token spend, and force expensive retrieval strategies (hybrid/MMR/rerank).
- The SaaS RAG path (`/rag/chat*`) shares the same schema but is authenticated/internal-only — out of scope per plan (policy mechanism reusable later if needed).
- Baseline: 1346 tests green before Phase E changes.

## 3. What Was Changed

| File | Change |
|---|---|
| `app/application/widget/policy.py` | NEW — `WidgetServerPolicy` (frozen dataclass, server-side bounds) + `apply_widget_policy()` + `WidgetPolicyResult`. Sanitizes every AI-execution control; records every deviation as a human-readable clamp |
| `app/api/widget/router.py` | `widget_chat` now runs the request through the policy before building `RAGRequest`; clamped controls are logged at WARNING with store + widget ids; tenant context wiring unchanged |

Policy bounds (defaults, fully configurable via `WidgetServerPolicy` constructor):

| Control | Default server policy |
|---|---|
| `model` | only allowlisted models; else server `DEFAULT_MODEL` (empty allowlist ⇒ server owns model) |
| `temperature` | clamped to [0.0, 1.0] (client may send 0–2); default 0.7 when absent |
| `max_tokens` | capped at 1024 |
| `top_k` | capped at 10 |
| `score_threshold` | floored at 0.0 |
| `use_hybrid` / `use_mmr` / `rerank` | forced `False` unless allowlisted |
| `knowledge_scope` | dropped unless in the allowlist |

Compatibility: `WidgetChatRequestSchema` is **unchanged** — legacy fields remain in the contract (a client sending every control at maximum still gets 200-level validation), they just cannot influence cost or behavior beyond the policy.

## 4. What Was NOT Changed

- `WidgetChatRequestSchema` / `WidgetChatResponseSchema` (contract preserved).
- SaaS RAG/recommendation/chat routes (authenticated, out of scope).
- Widget token model, scopes, tenant resolution.
- No endpoints added, removed, or deprecated → OpenAPI contract unchanged.

## 5. Tests Executed

| ID | Test | Result | Evidence |
|---|---|---|---|
| E-01 | Legacy schema still accepts hostile controls (compat adapter) | PASS | `test_legacy_schema_still_accepts_hostile_controls` |
| E-02 | Non-allowlisted / any client model → server default | PASS | `test_model_not_allowlisted_uses_server_default`, `test_empty_allowlist_blocks_all_client_models` |
| E-03 | Allowlisted model passes through | PASS | `test_model_allowlisted_passes` |
| E-04 | Temperature clamped to bounds; default when absent | PASS | `test_temperature_clamped_to_policy_bounds`, `test_temperature_default_when_absent` |
| E-05 | max_tokens / top_k capped; compliant values pass | PASS | `test_max_tokens_capped`, `test_max_tokens_within_policy_unchanged`, `test_top_k_capped` |
| E-06 | Hybrid/MMR/rerank forced off; allowlisted policy passes | PASS | `test_expensive_retrieval_flags_forced_off`, `test_retrieval_flags_allowlisted` |
| E-07 | knowledge_scope dropped unless allowlisted | PASS | `test_knowledge_scope_dropped_when_not_allowlisted`, `test_knowledge_scope_allowlisted` |
| E-08 | Fully compliant request → zero clamps | PASS | `test_in_policy_values_pass_unclamped` |
| E-09 | Router: hostile payload → clamped RAGRequest (200) | PASS | `test_hostile_controls_are_clamped_before_rag_service` |
| E-10 | Router: compliant payload unchanged | PASS | `test_compliant_request_passes_unchanged` |
| E-11 | Router: clamping logged with store + widget ids | PASS | `test_clamping_is_logged_with_store_and_widget` |
| E-12 | No warning when nothing clamped | PASS | `test_no_warning_when_nothing_clamped` |
| E-13 | Policy bounds are configurable | PASS | `test_policy_limits_are_configurable` |
| — | Full regression suite | PASS | **1365 passed** |
| — | Ruff lint + format | PASS | clean on all touched files |

## 6. Failures Found During Phase

None. (One test-authoring issue: `B008` function-call-in-default flagged by ruff → singleton `DEFAULT_WIDGET_POLICY`; also a lint self-inflicted edit slip caught by the suite.) No design failures.

## 7. API Impact

- Added endpoints: none
- Modified endpoints: `POST /api/v1/widget/chat` — request/response schemas unchanged; behavior now server-policy-bound (client AI controls sanitized)
- Deprecated endpoints: none
- Breaking changes: none (fields accepted as before; they are now clamped)

## 8. Database Impact

None.

## 9. Phase A Risk Register — Status

| Risk | Severity | Phase E outcome |
|---|---|---|
| R-03 widget exposes AI execution controls → uncontrolled cost/behavior | P2 | **Closed** — server policy + compatibility adapter; deviations logged |

## 10. Remaining Risks

| ID | Issue | Severity |
|---|---|---|
| E-R1 | Policy is global (server defaults); per-store / per-installation policy overrides not yet supported (fields exist on `WidgetServerPolicy`, wiring is future work) | P3 |
| E-R2 | SaaS `/rag/chat*` and `/chat` still honor client AI controls (authenticated internal callers only) | P3 |
| E-R3 | `knowledge_scope` semantics overlap with retrieval `RetrievalFilters`; allowlist default drops all client scopes — verify with integrations using scoped knowledge bases | P3 |

## 11. Exit Gate

**PASS**

- [x] E-01..E-13 pass (19 new tests)
- [x] Full regression 1365 passed, ruff clean
- [x] R-03 closed: server policy authoritative over all widget AI-execution controls
- [x] Compatibility adapter: legacy schema and fields unchanged
- [x] Deviations logged with tenant identity (audit trail)