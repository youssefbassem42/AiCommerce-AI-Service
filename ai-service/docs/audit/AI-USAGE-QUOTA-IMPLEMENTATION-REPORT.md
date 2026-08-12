# AI Usage Quota — Implementation Report

**Scope:** FastAPI AI runtime enforcement (store token quota, consumer daily quota, provider failover, usage reporting)
**Authority:** .NET owns plans/subscriptions/Stripe/billing; FastAPI enforces at runtime
**Status:** Implemented — unit tests green (1426 passed), ruff clean

---

## 1. Existing AI architecture inspected

| Area | State |
| --- | --- |
| TenantContext | Widget tokens minted by `WidgetTokenService` (`AI-Commerce-Widget` issuer) → `TenantContext` via `get_widget_tenant_context`; SaaS tokens via `AuthMiddleware` → `request.state` |
| Widget auth/session | `AuthMiddleware._dispatch_widget`; widget session identity is the token `jti` claim (server-side, anonymous consumers counted) |
| AI execution | `RagOrchestrationService.answer` (widget chat), `RecommendationService.recommend`, `ChatService` (SaaS), RAG SaaS/agents, provider adapters via `LLMProviderFactory` |
| ModelRegistry | `app/core/model_registry.py` maps model → provider/capabilities; reused for alias resolution and provider derivation |
| Redis | `app/infrastructure/redis/client.py` (plan cache); new `quota_scripts.py` for atomic counters |
| Mongo | `runtime_logs` collection via `AnalyticsRepository` — extended, not replaced |
| Rate limiter | Existing `RATE_LIMIT_WIDGET_*` request-rate limiting left untouched (spec §31) |
| Internal auth | Existing token/middleware architecture reused; no second tenant system created |

## 2. Plan context contract

- Trusted source: signed .NET access-token claims (login token path in `AuthMiddleware`).
- Ingested into the per-store `PlanPolicy` (Mongo, Redis-cached 5 min) by `PlanPolicyService.sync_from_claims` (fire-and-forget on auth; failures fall back to persisted/default policy).
- No browser/widget-supplied plan values are ever consulted (`apply_widget_policy(payload, widget_policy_from_plan(plan))`).
- Claim names currently read: `subscriptionStatus`, `numOfTokens`, `aiModels`, `planName`, `billing_period`, `renewal_date`, `consumer_daily_message_limit_max`, `billing_period_days`.
- Unknown/absent claims fall back to service defaults; a zero token limit fails closed (never unlimited).
- **Pending integration:** user will provide a .NET plan-context API endpoint (not finished yet). When it lands, `PlanPolicyService` resolution will be extended to consume it; the claims path remains the interim contract. No endpoint client was built (spec §34 — no speculative integrations).

## 3. Store token quota architecture

- Identity: `store_id + billing_period` (NOT store + calendar month, NOT plan + month).
- State per identity: `used` (committed) + `reserved` (in-flight), atomically kept ≤ `limit`.
- Pre-flight order (spec §7): resolve plan (fail closed) → consumer session limit (atomic) → store token reservation (atomic, budget-sized) → LLM execution → commit actual usage → release unused reservation → runtime log.

## 4. Billing-period handling

- `billing_period` from .NET claims when present; otherwise a period identity derived at first provision (`{store_id}:{iso}`, `derived_period_id`) anchored to `period_start`.
- While the subscription period is active, the period ID is stable across syncs — an upgrade (Starter→Pro) mutates entitlement only, usage counter key unchanged (spec §54: no reset).
- At `period_end`, `PlanPolicyService._roll_period` opens a new period identity; the counter key changes → fresh quota; historical `runtime_logs` remain queryable by old period (spec §55).
- Downgrade: no logic in FastAPI (spec §56). .NET supplies the new entitlement at the new period.

## 5. Reservation algorithm (store tokens)

1. `StoreTokenQuotaService.reserve(plan, budget)` → single Redis `EVAL` of `TOKEN_RESERVE_LUA`.
2. Script: `available = limit - used - reserved`; `available < requested → reject {0, used, reserved, available}`; else `reserved += requested`, `EXPIRE`.
3. LLM executes; actual provider usage normalized.
4. `finalize(plan, reservation, actual)`:
   - `TOKEN_COMMIT_LUA`: `used += actual`, `reserved -= actual`.
   - leftover `= requested - actual` released via `TOKEN_RELEASE_LUA`.
5. Never GET→calculate→SET; every mutation is one Lua script (spec §9, §15).
6. Commit uses honest provider-reported consumption (decision: no clamping; a single oversized request may push `used` marginally over limit — self-correcting, subsequent requests blocked).

## 6. Redis keys

| Key | Type | Purpose |
| --- | --- | --- |
| `ai:quota:{store_id}:{billing_period}` | hash `used, reserved` | Store token quota counter (TTL `QUOTA_REDIS_TTL_DAYS`=90d) |
| `ai:consumer:{store_id}:{session_id}:{date}` | string | Consumer daily message counter (TTL to end of UTC day) |
| `plan:policy:{store_id}` | string JSON | Plan policy cache (TTL 300s) |

## 7. Atomicity guarantees

- Redis `EVAL` executes each Lua script atomically (concurrent EVALs serialize on the server).
- Concurrency test (§48): limit 1000, 900 reserved (100 available), 20 concurrent × 20 tokens → exactly 5 pass; final used+reserved = 1000.
- Consumer concurrency: limit 15, 15 concurrent → exactly 15 pass; 16th rejected with `CONSUMER_DAILY_LIMIT_EXCEEDED`.

## 8. Token calculation

- Centralized in `UsageNormalizer` (spec §12-13, §40): canonical `prompt_tokens / completion_tokens / total_tokens` with `total = prompt + completion`.
- Provider-reported actual usage wins; estimation (`calculate_tokens`) only when a provider reports nothing and for pre-flight budget sizing (`estimate_budget`, context-length-capped, headroom `QUOTA_BUDGET_HEADROOM`=2.0).
- Multi-LLM-call turns aggregate via `QuotaRunState.record` (contextvar) — chat, RAG, agents, recommendations share one path.

## 9. Consumer session quota

- Key: `store + session_id + UTC date` — anonymous visitors counted (session = server-side widget-token `jti`).
- `ConsumerQuotaService.reserve_message` = single atomic `CONSUMER_RESERVE_LUA` (`limit<=0` or `used>=limit` → reject; else `INCR` + `EXPIRE` to midnight).
- Plan hard maximum `consumer_daily_message_limit_max` (from .NET); store-owner override via `PUT /api/analytics/ai-usage/consumer-limit` (`0 ≤ limit ≤ max`, `ConsumerLimitOutOfRangeError` → 422).
- A session belonging to store A cannot consume store B quota (store is part of the key; enforcer resolves plan per store).

## 10. Provider selection

- `ProviderSelector.provider_order`: allowed providers ordered with `DEFAULT_PROVIDER` first.
- `model_for_provider`: requested model only if plan-allowed on that provider, then plan fallback, then first allowed model of provider. Consumer can never pick provider/model (spec §44-45).
- `widget_policy_from_plan` clamps widget-chat controls to plan-allowed models.

## 11. Provider failover

- Triggers: `ProviderUnavailableException`, `RateLimitException` (includes provider API-quota exhaustion), `AuthenticationException`, `StreamingException`, `TimeoutError`.
- First plan-allowed provider success wins; failures fall through to the next allowed provider; a disallowed provider is never selected.
- Reservation accounting: usage only recorded per successful provider; failed providers produce no charge; a failed turn releases the full reservation (`_release_on_failure`).
- All plan-allowed providers failed → `AllProvidersFailedException` (`AI_PROVIDER_UNAVAILABLE`, 503); quota is not bypassed.
- `PlanFailoverProvider` facade (BaseLLMProvider) feeds orchestration workflows/agents/ChatService during an active quota run without redesigning them.

## 12. Usage persistence

- Extends existing `runtime_logs` — new fields only: `store_id`, `organization_id`, `billing_period`, `provider`, `completion_tokens`, `total_tokens`, `cost`, `session_id` (plus existing `prompt_tokens`). Indexes added: `(store_id, billing_period, timestamp)`, `(store_id, provider, timestamp)`, `(store_id, model, timestamp)`.
- `RuntimeUsageLogger.log` records one row per enforced execution.

## 13. Usage reporting

- `GET /api/analytics/ai-usage` (existing analytics router, authenticated, store-scoped, cross-store `store_id` query param rejected 403).
- Response: plan, subscription status, billing period (id/start/end/renewal_date), tokens (limit/used/reserved/remaining/percentage), requests, prompt/completion tokens, cost, consumer daily limit (effective + max), provider breakdown, model breakdown.

## 14. Provider breakdown

Per provider: requests, prompt_tokens, completion_tokens, total_tokens, cost — from Mongo `$group` on `provider` filtered by `store_id + billing_period` (spec §38).

## 15. Model breakdown

Per model: requests, total_tokens, cost — `$group` on `model`, same scoping (spec §39).

## 16. Error behavior

| Condition | Code | HTTP |
| --- | --- | --- |
| Store quota exhausted | `STORE_TOKEN_QUOTA_EXCEEDED` | 429 — limit, used, reserved, available, billing_period_end |
| Consumer daily limit reached | `CONSUMER_DAILY_LIMIT_EXCEEDED` | 429 — limit, used, reset_at |
| All providers failed | `AI_PROVIDER_UNAVAILABLE` | 503 |
| Redis unavailable (fail closed) | `QUOTA_UNAVAILABLE` | 503 |
| Unusable plan / inactive subscription / zero token limit / empty provider policy | `PLAN_NOT_AVAILABLE` | 403 |

Safe info only; no provider keys, no internal health, no other tenants (spec §51, §53).

## 17. Tenant isolation

- Quota keys and plan policies are store-scoped; consumer keys store+session scoped.
- Usage aggregation always filtered by `store_id` (+billing_period); analytics API rejects mismatched `store_id`.
- Tests: store A/B quota and consumer isolation, session isolation, same-store different-period isolation.

## 18. Concurrency tests

- `test_twenty_concurrent_requests_only_five_pass`: limit 1000, 100 available, 20×20 → exactly 5 succeed; final counters = 1000 (no overshoot).
- `test_limit_fifteen_rejects_sixteenth_under_race`: 15 concurrent vs limit 15 → exactly 15 pass; extra rejected at 15/15.

## 19. Failure tests

- Redis unavailable → `QuotaUnavailableError` → `QUOTA_UNAVAILABLE` (fail closed; `QUOTA_FAIL_OPEN` default False).
- Provider unavailable/quota-exhausted/credential failure → failover to allowed provider.
- All providers unavailable → `AI_PROVIDER_UNAVAILABLE`.
- Invalid trust (token_limit=0, canceled subscription) → `PLAN_NOT_AVAILABLE`.
- Reservation released on execution failure; no log row on failure.

## 20. API changes

- `GET /api/analytics/ai-usage` — usage report (new).
- `PUT /api/analytics/ai-usage/consumer-limit` — store-owner consumer limit (new).
- Widget `POST /api/widget/chat` and `POST /api/widget/recommendations` — wrap execution in `QuotaEnforcer` (behavior otherwise unchanged).
- `WidgetChatRequestSchema` unchanged; `RAGRequest` gains server-internal `fallback_providers`.
- Error envelope: `code` + `details` now surfaced through `ai_exception_handler`.

## 21. Files changed

Modified:
- `app/api/analytics/router.py`, `app/api/analytics/schemas.py`
- `app/api/rag/dependencies.py`, `app/api/widget/router.py`
- `app/application/rag/dto.py`, `app/application/rag/service.py`
- `app/application/services/chat_service.py`
- `app/application/widget/policy.py`, `app/application/widget/token_service.py`
- `app/core/ai_exceptions.py`, `app/core/config.py`, `app/core/exception_handlers.py`
- `app/domain/analytics/entities/runtime_log.py`, `app/domain/analytics/repositories/analytics_repository.py`
- `app/infrastructure/mongodb/collections.py`, `documents/runtime_log_document.py`, `indexes.py`, `repositories/analytics_repository.py`, `validators.py`
- `app/middleware/auth.py`, `tests/unit/modules/widget/test_widget_policy.py`

New:
- `app/core/plan_context.py`
- `app/application/quota/{enforcer,plan_policy,counter_store,store_token_quota,consumer_quota,provider_selector,usage_normalizer,runtime_usage_logger,usage_reporting,run_context}.py`
- `app/api/quota/dependencies.py`
- `app/infrastructure/redis/quota_scripts.py`
- `app/domain/analytics/entities/plan_policy.py` + domain/mongo repositories + `store_plan_policy_document.py`
- `tests/unit/quota/{conftest,test_plan_policy,test_store_token_quota,test_consumer_quota,test_enforcer,test_provider_selector,test_usage_normalizer,test_usage_reporting}.py`
- This report.

## 22. Tests executed

- `pytest tests/unit` (excl. integration needing live infra): **1426 passed, 0 failed**, 76s.
- Quota unit suite: 98 tests — reservation under/at/over limit, commit, release, finalize reconciliation, concurrent store reservation, concurrent consumer reservation, isolation (store/session/period), failover (all trigger classes, all-failed), disallowed provider never used, plan fail-closed, Redis fail-closed, upgrade-keeps-period, new-period roll, consumer limit cap, reporting totals/breakdowns/percentage/remaining.
- `ruff check` on all touched modules: clean.

## 23. Regression results

- Existing widget tests (`test_widget_bootstrap`, `test_widget_policy`, `test_widget_token`) pass with enforcer overrides.
- Existing auth middleware tests pass with claim-sync added.
- Existing analytics/repositories untouched paths pass; `runtime_logs` schema validator extended without breaking existing writes.

## 24. Performance impact

- Reservation/commit/release: one EVAL each (µs-class) — negligible.
- Plan resolution: Redis-cached 300s; Mongo only on cache miss/expiry. Auth-time claim sync is fire-and-forget (never blocks the request).
- Reporting: 3 indexed `$group` aggregations over the store's period (indexes on store+period). For very large periods, results are load-reducing candidates via an hourly rollup — **not implemented** (out of scope).

## 25. Security impact

- Commercial quota fails closed when Redis is unavailable (`QUOTA_FAIL_OPEN` defaults off; operator override logged loudly).
- Plan context only from signed .NET tokens; browser-supplied plan never trusted.
- Error payloads carry only limit/used/reset data — no credentials, no provider health, no architecture details.
- Cross-store reporting blocked at API (claim match) and query (store filter) layers.
- Consumer counting uses server-side session id (unsigned jti from widget token, validated at widget auth) — spoofing only affects the attacker's own session counter.

## 26. Out-of-scope items (spec §34, §58)

- Subscription/Stripe/billing-cycle/renewal/trial/upgrade/downgrade management — .NET owns all.
- Plan CRUD and Super Admin plan management.
- New provider integrations.
- Downgrade activation logic.
- SaaS-side (`/api/ai/**`) AI endpoint quota enforcement — decision: widget-only enforcement; SaaS paths retain existing behavior (ChatService failover facade applies only while a quota run is active, which is widget-triggered).
- Provider circuit breakers / permanent provider disabling (not supported by existing architecture).
- Any calendar-month quota identity (spec §57) — daily consumer key uses date by design (spec §25), store quota never does.

## 27. Remaining risks

1. **.NET plan-context endpoint pending** — claims are the interim contract; claim names above must be confirmed/linked once the endpoint exists. The policy layer (`PlanPolicyService.sync_from_claims`) is the single seam to extend.
2. **No live-Redis integration test** — unit tests emulate Lua semantics in-process (`FakeLuaCounterStore`); a staging smoke test against real Redis is recommended before release.
3. **Mongo aggregation tested via mocks** — live `aggregate_usage` should be verified in staging.
4. Pre-flight budget is an estimate; actual usage beyond reservation is committed honestly and self-correcting (overage can transiently push `used` past limit by one request).
5. `QUOTA_REDIS_TTL_DAYS` (90d) assumes system clock/Redis persistence sane; a Redis restart loses counters (used=0 until plan re-sync) — acceptable for current contract, can be hardened with Mongo checkpoints if needed.

## 28. Conflicts discovered

- **None blocking.** Considered-and-resolved decision: metering identity splits commercial quota (billing period) from rate limit (requests/min) and consumer quota (session/day) — three separate controls per spec §30-31; existing request-rate limiter untouched.
- Pending user decision recorded: widget-only enforcement scope; honest (unclamped) commit accounting; claims-first plan context with later .NET API endpoint.