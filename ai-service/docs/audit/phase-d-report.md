# Phase D Report — Endpoint-Aware Rate Limiting

## 1. Status

**PASS**

## 2. What Was Audited

- `app/middleware/rate_limit.py` — single global limiter (100 req/min) keyed by `store_id` (if set by `AuthMiddleware`, which runs outer to the limiter) or client IP, with a Redis fixed-window primary and a bounded in-memory sliding-window fallback; only `/health` whitelisted. **Conclusion:** no endpoint awareness, no widget-session identity, no widget-key identity (Phase A R-08/R-09).
- Route inventory (endpoint ownership matrix + routers): cost-heavy LLM routes (`/chat`, `/api/v1/ai/chat*`, `/rag/chat*`, `/api/v1/recommendations/*`, `/api/v1/widget/chat|recommendations`), widget bootstrap (`/api/v1/widget/bootstrap`, `X-Widget-Key` header), widget session endpoints.
- `AuthMiddleware` ordering: runs before the rate limiter, so `request.state.store_id` (SaaS and widget JWTs alike) is available when the limiter executes.
- Baseline: 1330 tests green before Phase D changes.

## 3. What Was Changed

| File | Change |
|---|---|
| `app/middleware/rate_limit.py` | Tiered checks: `default` (unchanged semantics), `llm` (`llm:{identity}`, tighter per-store/IP cap on cost-heavy routes), `widget_session` (per widget store), `widget_bootstrap` (SHA-256 hash of `X-Widget-Key`). First tripping tier → 429 with `tier`/`limit`/`reset_seconds` + `Retry-After`; response headers extended with `X-RateLimit-Tier` on 429; success headers unchanged (default tier) |
| `app/core/config.py` | `RATE_LIMIT_LLM_PER_MINUTE=20`, `RATE_LIMIT_WIDGET_BOOTSTRAP_PER_MINUTE=30`, `RATE_LIMIT_WIDGET_SESSION_PER_MINUTE=60` (env-configurable) |
| `app/main.py` | Registers the new tier limits on `RateLimitMiddleware` |
| `.env.example` | Rate limiting section with the four `RATE_LIMIT_*` variables |
| `tests/conftest.py` | All four tier limits raised to 1,000,000 in the test env (existing pattern) |
| `tests/unit/middleware/test_rate_limit_tiers.py` | NEW — 16 tests: tier resolution + dispatch enforcement |
| `docs/security.md` | Rate limiting section rewritten: tier table, keys, headers, env vars |

## 4. What Was NOT Changed

- `_get_rate_limit_key` behavior (`store:{store_id}` / `ip:{ip}`) — existing key-derivation tests untouched and passing.
- Redis fixed-window + in-memory sliding-window store mechanics; whitelist (`/health`, `/health/`).
- Default tier limit semantics (100 req/min) and success-path headers.
- No endpoint added/removed/deprecated; OpenAPI contract unaffected (middleware-level).

## 5. Tests Executed

| ID | Test | Result | Evidence |
|---|---|---|---|
| D-01 | Key derivation unchanged (store / ip) | PASS | `test_rate_limit.py` (legacy, untouched) |
| D-02 | Default route → single `default` check | PASS | `test_default_route_single_check` |
| D-03 | RAG / AI chat / plain chat → `llm` tier present | PASS | `test_rag_chat_gets_llm_tier`, `test_ai_chat_stream_gets_llm_tier`, `test_plain_chat_endpoint_gets_llm_tier` |
| D-04 | Bootstrap → hashed widget-key check; raw key never in store | PASS | `test_widget_bootstrap_gets_key_tier`, `test_raw_widget_key_never_enters_local_store` |
| D-05 | Bootstrap without key → no key tier (identity fallback) | PASS | `test_widget_bootstrap_without_key_falls_back_to_identity` |
| D-06 | Widget chat → session + llm + default tiers | PASS | `test_widget_chat_gets_session_and_llm_tiers` |
| D-07 | Widget keys hash distinctly | PASS | `test_widget_key_hashes_are_distinct` |
| D-08 | LLM tier trips independently of default | PASS | `test_llm_tier_trips_before_default` |
| D-09 | Bootstrap 429 per key; other key unaffected (R-09) | PASS | `test_widget_bootstrap_is_limited_per_key` |
| D-10 | Widget session 429 per store; other store unaffected (R-08) | PASS | `test_widget_session_trips_per_store` |
| D-11 | Default tier still applies | PASS | `test_default_tier_still_applies` |
| D-12 | Success headers report default tier | PASS | `test_success_response_reports_default_tier_headers` |
| D-13 | 429 body/headers include tier, limit, Retry-After | PASS | asserts in `test_llm_tier_trips_before_default` |
| — | Full regression suite | PASS | **1346 passed** |
| — | Ruff lint + format | PASS | clean on all touched files |

## 6. Failures Found During Phase

| Finding | Severity | Fix |
|---|---|---|
| Sharing the identity key across tiers let the default-tier counter eat the LLM-tier budget (the "empty bucket" effect: a chat request consumed the same 20/min from a shared timestamp list) | P1 (design bug caught by D-08) | LLM tier uses its own namespace key `llm:{identity}`; each tier has an independent bucket per the intended semantics |

## 7. API Impact

- Added endpoints: none
- Modified endpoints: none (behavioral change only on 429 responses: added `tier` to the body; `X-RateLimit-Tier` response header on 429)
- Deprecated endpoints: none
- Breaking changes: none (limits are higher or equal to 100 for the default tier; tighter tiers apply only to cost-heavy routes by design)

## 8. Database Impact

None. Redis keys are namespaced per tier (`rate_limit:{key}:{window}`) and auto-expire; memory store remains bounded (10,000 keys with stale eviction).

## 9. Phase A Risk Register — Status

| Risk | Severity | Phase D outcome |
|---|---|---|
| R-08 no per-endpoint / per-widget-session rate limits | P2 | **Closed** — llm + widget_session tiers |
| R-09 `X-Widget-Key` not rate-limited | P2 | **Closed** — hashed-key tier on bootstrap |

## 10. Remaining Risks

| ID | Issue | Severity |
|---|---|---|
| D-R1 | Rate limits are per-minute fixed/sliding windows; sustained distributed bot traffic across many IPs still lands within limits | P3 |
| D-R2 | Redis downtime degrades to the in-memory window (single-instance state) — acceptable fallback, revisit if multi-replica deploy occurs | P3 |
| D-R3 | `RATE_LIMIT_*` values are static env config; no per-plan/per-store-tier overrides yet | P3 |

## 11. Exit Gate

**PASS**

- [x] D-01..D-13 pass (16 new tests)
- [x] Full regression 1346 passed, ruff clean
- [x] R-08/R-09 closed with per-widget-session and per-widget-key limits
- [x] Raw widget keys never stored or logged (SHA-256 only)
- [x] Existing success-path header contract unchanged