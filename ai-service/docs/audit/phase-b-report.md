# Phase B Report — Request Correlation & Observability

## 1. Status

**PASS**

## 2. What Was Audited

- `app/middleware/logging.py` (`AITracingMiddleware`) — the pre-existing correlation mechanism: generated/extracted `X-Correlation-ID` per request, stored on `request.state.correlation_id`, echoed on the response, and logged on every request. **Conclusion:** `X-Correlation-ID` and the plan's `X-Request-ID` represent the same concept — one identifier, not two.
- `app/application/services/chat_service.py` — internal `correlation_id` argument + `_generate_correlation_id()` (UUID) used for `[AI Metrics]` structured logs.
- `app/middleware/audit.py` — audit log writer (non-GET requests → `audit_logs`).
- Runtime log attempts: the `runtime_logs` collection, `AIRuntimeLog` entity, `AIRuntimeLogDocument`, `AnalyticsRepository` and a Mongo validator all exist, but **no application code ever writes `AIRuntimeLog`** (no writer found). The de-facto runtime observability channel today is the structured `[AI Metrics]` log line + `audit_logs`.
- `TenantContext` — lacked a correlation field.
- All 1371 tests as regression baseline.

## 3. What Was Changed

| File | Change |
|---|---|
| `app/core/request_context.py` | NEW — contextvar `request_id` + `get_request_id()`/`set_request_id()`/`new_request_id()` for the whole stack |
| `app/middleware/request_context.py` | NEW — `RequestContextMiddleware`: honors `X-Request-ID`, accepts `X-Correlation-ID` as legacy alias, generates UUID otherwise; sets `request.state.request_id` (+ legacy `correlation_id`); echoes `X-Request-ID` AND `X-Correlation-ID` on responses (legacy header behavior preserved); no secrets logged |
| `app/middleware/logging.py` | `AITracingMiddleware` now consumes `request.state.request_id` (fallback UUID) — tracing only, no competing ID generation; response header `X-Correlation-ID` now set by the outer middleware |
| `app/main.py` | Registers `RequestContextMiddleware` outermost (added last), with explicit ordering comment |
| `app/domain/knowledge/value_objects/tenant_context.py` | Added `request_id: str = ""` field (backward compatible, has default) |
| `app/application/rag/resolver.py` | `from_claims(...)` forwards `request_id` |
| `app/api/rag/dependencies.py` | `get_tenant_context` passes `request.state.request_id` into claims |
| `app/api/widget/dependencies.py` | `get_widget_tenant_context` sets `request_id` on the context |
| `app/application/services/chat_service.py` | `chat()`/`stream()` resolve `corr_id = correlation_id → request_id (contextvar) → UUID`. One identifier; explicit arg still wins |
| `app/middleware/audit.py` | Audit `detail` now includes `request_id` |
| `tests/unit/middleware/test_request_context.py` | NEW — B-01..B-05 plus alias and token-contract guards |

## 4. What Was NOT Changed

Preserved: all 105 API contracts (verified byte-identical OpenAPI diff vs baseline), the widget JWT contract, the LLM provider abstraction, RAG engine, MongoDB/vector stack, middleware behavior of `AuthMiddleware`/`RateLimitMiddleware`/`WidgetCorsMiddleware`/`AuditMiddleware` (only additive `request_id` detail), and the `X-Correlation-ID` response header contract.

## 5. Tests Executed

| ID | Test | Result | Evidence |
|---|---|---|---|
| B-01 | Incoming `X-Request-ID` echoed (value, both headers) | PASS | `test_b01_incoming_request_id_is_echoed` |
| B-02 | Missing header → valid UUID generated + echoed | PASS | `test_b02_missing_header_generates_uuid_and_echoes` |
| B-02a | Legacy `X-Correlation-ID` accepted as alias | PASS | `test_b02_legacy_x_correlation_id_accepted_as_alias` |
| B-03 | RAG/chat metrics log lines carry the same `request_id` | PASS | `test_b03_chat_metrics_use_request_id` (caplog, contextvar) |
| B-04 | Widget chat tenant context carries `request_id` | PASS | `test_b04_widget_tenant_context_carries_request_id` |
| B-05 | Streaming response carries the request ID end-to-end | PASS | `test_b05_streaming_response_carries_request_id` |
| B-06 | Widget token contract unchanged (guard) | PASS | `test_b06_widget_token_roundtrip_unchanged` |
| — | Full regression suite | PASS | 1371 passed (1364 baseline + 7 new) |
| — | OpenAPI byte-diff vs baseline | PASS | `diff` identical |

## 6. Failures Found

None.

## 7. Fixes Applied

| Problem | Change | Files | Reason | Compatibility impact |
|---|---|---|---|---|
| Two competing correlation concepts | One identifier: `X-Request-ID` canonical, `X-Correlation-ID` legacy alias; removed ID generation from tracing middleware | request_context.py, logging.py, chat_service.py | Plan B2 — no duplicate identifiers | None (`X-Correlation-ID` still echoed and accepted) |
| `request_id` unavailable below the API layer | Contextvar + TenantContext field | core/request_context.py, tenant_context.py, resolver/deps | Propagation HTTP→API→service→LLM/log | None (field has default) |
| Audit entries uncorrelated | `request_id` added to audit `detail` | middleware/audit.py | Runtime-log correlation | None (additive field) |

## 8. Security Impact

Improved: every request now has a server-verifiable correlation ID usable to trace cross-tenant incident activity; audit and AI metrics are joinable. No secrets are logged; the middleware never logs header values.

## 9. Production Impact

Minimal: two extra response headers (`X-Request-ID`, and the previously-existing `X-Correlation-ID` keeps its behavior). Nothing else changes.

## 10. API Impact

- Added endpoints: none
- Modified endpoints: none (response headers only, not part of the OpenAPI contract — verified byte-identical)
- Deprecated endpoints: none
- Breaking changes: none

## 11. Database Impact

No schema changes, no indexes, no migrations. Audit log documents now contain an additional `details.request_id` key on new entries (old entries unaffected).

## 12. Remaining Risks

| ID | Issue | Severity |
|---|---|---|
| B-R1 | `AIRuntimeLog` (`runtime_logs` collection) has no application writer — runtime observability lives in structured logs + audit_logs; a dedicated runtime-log writer (with `request_id`, tenant, widget/conversation IDs) is still open (Phase 3 of the original roadmap / backlog) | P2 |
| B-R2 | Streaming disconnect leaves no explicit log record of aborted streams | P3 |
| B-R3 | `X-Request-ID` is not validated for length/format (accepts arbitrary strings) — acceptable for correlation, revisit if used for log injection defenses | P3 |

## 13. Required Action

| Issue | Severity | Action | Owner | Blocking? |
|---|---|---|---|---|
| B-R1 | P2 | Decide runtime-log writer scope (widget runtime logging is a Phase-3-style feature); track in backlog | AI service | No |
| B-R2 | P3 | Add stream-abort logging when implementing widget streaming | AI service | Phase E |
| B-R3 | P3 | Optionally cap header length at 128 chars | AI service | Backlog |

## 14. Exit Gate

**PASS**

- [x] B-01..B-05 correlation tests pass
- [x] Existing API behavior unchanged except the intended response headers (OpenAPI identical)
- [x] Single identifier concept documented and implemented
- [x] Correlation available HTTP → TenantContext → service → chat metrics → audit log