# Widget Integration Audit — Auth, Tenant Isolation, Security (Phases 2–4)

> Findings from auditing the current widget bundle (`/home/youssef/AI-Compliance/widget`)
> against the current FastAPI backend (`ai-service/`, HEAD `b7d3e48`) and live production
> (`https://aicommerce-ai-service-production.up.railway.app`).
> Audit date: 2026-08-13. All findings were verified against source and (where noted) live.

---

## Phase 2 — Authentication audit

### Backend (verified)

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| A1 | Widget key sent ONLY to bootstrap | ✅ | `WidgetBootstrapService.bootstrap` accepts `X-Widget-Key`; `ApiClient` attaches it only when `isBootstrap: true` (src/api/ApiClient.js:86-96) |
| A2 | Widget key stored hashed (SHA-256), never persisted readable | ✅ | `bootstrap_service.py:_resolve_installation` hashes key with sha256; repository stores only the hash |
| A3 | Session token short-lived (default 15 min), scoped | ✅ | `token_service.py:create_session_token` — `exp` = now + `WIDGET_TOKEN_TTL_MINUTES*60`; claims carry `scopes` |
| A4 | Token issuer/audience distinct from SaaS (`AI-Commerce-Widget`) | ✅ | `token_service.py` — `ISSUER/AUDIENCE = auth_settings.WIDGET_ISSUER/WIDGET_AUDIENCE`; `AuthMiddleware.dispatch` peeks issuer and routes to widget path; SaaS path never sees widget tokens |
| A5 | Widget token cannot access SaaS endpoints | ✅ | `_dispatch_widget` sets `request.state.user=None, roles=[]`; SaaS deps (`get_current_user`, `get_current_store_id`, `require_admin_role`) require `user`/`store_id` → 401/403 |
| A6 | Bootstrap failures indistinguishable (generic 401/403) | ✅ | `router.py` maps `WidgetInstallationNotFoundError`/`WidgetOriginNotAllowedError` → `detail="Invalid widget key"` |
| A7 | Origin allow-list enforced at bootstrap; no wildcard | ✅ | `_assert_origin_allowed` — origin must be in `allowed_origins`; wildcard never permitted |
| A8 | Strict token validation (sig, exp, iss, aud, required claims) | ✅ | `token_service.validate` — all verify_* options on, `require` list enforced; scopes must be a non-empty string list |
| A9 | Widget token rate limit by key-hash + session | ✅ | `rate_limit.py` — bootstrap keyed by SHA-256 of key (R-09), chat/recommendations by session store_id (R-08) |

### Widget (verified in bundle + source)

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| W1 | Token held in memory only (never localStorage/sessionStorage/cookies/IndexedDB) | ✅ | `WidgetAuthManager` closure field `_token`; grep of `dist/widget.js` for `localStorage|sessionStorage|document.cookie|eval(` → 0 hits |
| W2 | Single 401 → one controlled re-bootstrap → one retry | ✅ | `ApiClient.request` (src/api/ApiClient.js:122-136): `if (error.isAuth() && auth && this.bootstrap && !this._authRetried)` → bootstrap → `continue` (retry once); `shouldRetry` never retries 401/429/4xx |
| W3 | **FIXED (this audit):** retry flag never reset after success | ✅ Fixed | `resetAuthRetry()` was defined but never called — a second token-expiry incident in the same widget session would not re-bootstrap. Now reset on any 2xx (ApiClient.js). Verified: bundle rebuilt, 11/11 tests pass. |
| W4 | No infinite retry loops | ✅ | `_authRetried` guards bootstrap-recovery; `MAX_RETRIES=1` for network/5xx; 429 never auto-retried |
| W5 | Token not logged / not attached to host page | ✅ | `WidgetAuth` never logs key/token; `installGlobalSurface` exposes only `{version, mount, getWidget}` |
| W6 | Lazy bootstrap (only when protected request needed) | ✅ | `WidgetAuthManager.bootstrap` called from `ensureToken()` and on first `open()` |
| W7 | Bootstrap single-flight (concurrent callers share one promise) | ✅ | `_inFlight` in `WidgetAuthManager` |

### Auth issues found
1. **Fixed (W3):** `_authRetried` never reset → second 401 incident later in session would surface an error instead of one re-bootstrap+retry. Fixed and verified.
2. **Note (not a defect):** `WidgetAuthManager.expiresInSeconds` computes against the `now` function; expiration margin 30s is reasonable for 15-min TTL.

---

## Phase 3 — Tenant isolation audit

### Backend (verified)

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| T1 | Tenant (store_id, organization_id, widget_id) resolved server-side from token claims only | ✅ | `get_widget_tenant_context` (app/api/widget/dependencies.py) — reads `request.state.store_id/organization_id/widget_id` populated by `_dispatch_widget` from validated claims; raises 401 if any missing |
| T2 | Client-supplied tenant identifiers never consulted | ✅ | Widget chat/recommendations take `customer_id` (consumer id) only; `store_id`/`organization_id` are never read from the request body/query |
| T3 | Conversation ownership enforced | ✅ | `widget_chat` — `conversation_owned_by_store(payload.conversation_id, tenant_context.store_id)` → 404 if not owned |
| T4 | Cross-store access impossible with widget token | ✅ | Widget token claims are minted per installation; `get_widget_tenant_context` binds every widget request to that installation's store/org |
| T5 | Quota enforced per store | ✅ | `enforcer.run(store_id=tenant_context.store_id, ...)` in both widget chat and recommendations |

### Widget (verified)

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| W-T1 | Widget never invents store_id/organization_id | ✅ | `ChatService` body = `{message, conversation_id, customer_id?}` only; no tenant fields |
| W-T2 | Widget never stores/uses tenant ids from host page | ✅ | Config reads only widgetKey/apiBaseUrl/providerName/title/.../customerId — no store/org inputs |
| W-T3 | customer_id optional and consumer-scoped | ✅ | `_resolveCustomerId` — only sent when explicitly configured; truncated to 256 chars; never used as store/org |

### Tenant issues found
- None. The widget never touches tenant identity; the backend is the sole authority (confirmed by `tenant-isolation-matrix.md` C1–C10 + widget path C5).

---

## Phase 4 — Security audit

### Backend (verified)

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| S1 | CORS — dynamic origin resolution, never wildcard | ✅ | `WidgetCorsMiddleware` resolves origin against active installations (via cache), allows only configured origins |
| S2 | CORS allows required widget headers | ✅ | `Authorization`, `Content-Type`, `Accept`, `Origin`, `X-Widget-Key`, `X-Correlation-ID`; exposes `X-RateLimit-*`, `X-Correlation-ID` |
| S3 | Rate limiting on bootstrap/chat/recommendations | ✅ | `RateLimitMiddleware` — widget-key tier + widget-session tier + LLM tier |
| S4 | Static widget artifacts whitelisted from IP rate limits | ✅ | `PUBLIC_STATIC_PATHS = ("/widget.js", "/demo", "/demo/")` |
| S5 | No secret leakage in logs | ✅ | Rate limiter hashes keys; bootstrap logs generic errors; no key/token in logger calls |

### Widget (verified in bundle + source)

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| W-S1 | No `innerHTML`/`insertAdjacentHTML` for untrusted data | ✅ | `dom.js` uses `textContent` everywhere; `check.mjs` asserts no `innerHTML` in bundle |
| W-S2 | URL validation for links/images (http(s)/mailto only) | ✅ | `sanitizer.js` `isSafeUrl` + `createSafeLink` (`rel="noopener noreferrer nofollow"`); images only when `isSafeUrl` |
| W-S3 | Text sanitization (control/bidi/zws chars stripped) | ✅ | `safeText` strips `\u0000-\u001F`, zero-width, bidi control ranges |
| W-S4 | No secrets logged | ✅ | Widget only logs state transitions in debug mode; never logs key/token/headers |
| W-S5 | Shadow DOM isolation | ✅ | `attachShadow({mode:"open"})`; no global CSS/JS from widget |
| W-S6 | `credentials: "omit"`, `cache: "no-store"` on all requests | ✅ | `ApiClient._fetchJson` |
| W-S7 | Error messages never leak backend details | ✅ | `WidgetApiErrorHandler` maps every status to a static friendly message; raw `detail` used only for heuristic classification, never rendered |
| W-S8 | `provider_name` never consumer-supplied | ✅ | Config-only (`DEFAULT_PROVIDER_NAME="openai"`); test "provider name never comes from host UI / DOM text" passes |

### Security issues found
- **None.** The widget's security posture matches the backend contract (Shadow DOM, sanitizer, no storage, no secrets).

---

## Summary

- **Auth:** Sound; one defect found and fixed (W3 — retry flag reset).
- **Tenant isolation:** Sound; widget has no tenant surface.
- **Security:** Sound; no findings.

Audit evidence: `dist/widget.js` (grep assertions), `scripts/check.mjs`, backend files listed above, live production OpenAPI dump `/tmp/opencode/prod-openapi.json`.