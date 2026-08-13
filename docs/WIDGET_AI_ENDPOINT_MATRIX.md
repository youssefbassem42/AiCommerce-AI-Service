# Widget ↔ AI Service — Endpoint Matrix

> **Source of truth:** current FastAPI implementation at `ai-service/` (git HEAD `b7d3e48`)
> and the **live production OpenAPI** at `https://aicommerce-ai-service-production.up.railway.app/openapi.json`
> (dumped to `/tmp/opencode/prod-openapi.json`, 156701 bytes, 90 paths).
>
> Verified live against production on 2026-08-13.

## How to read this matrix

| Status | Meaning |
| --- | --- |
| `WIDGET-COMPATIBLE` | The widget CAN call this endpoint today with a widget session token (or public key flow). |
| `WIDGET-IMPLEMENTED` | The endpoint is widget-compatible **and** the widget bundle already calls it. |
| `ADMIN-ONLY` | Requires a SaaS admin JWT (`require_admin_role`). Not callable with a widget token. |
| `SAAS-ONLY` | Requires a SaaS user/store JWT (`get_current_user`). Not callable with a widget token. |
| `PUBLIC` | No authentication (static artifacts, health, docs). |

Auth model (verified in source + live):
- The OpenAPI declares **no security schemes**; authentication is enforced by
  `app/middleware/auth.py` (Bearer JWT) + explicit dependencies.
- Widget tokens (issuer `AI-Commerce-Widget`, scopes `rag:chat`, `recommendations:read`)
  are dispatched by `AuthMiddleware._dispatch_widget` and **never** carry a SaaS
  user identity, so they are rejected by every SaaS/admin dependency.
- Bootstrap uses `X-Widget-Key` (SHA-256 hashed server-side, generic 401/403, never
  wildcard origin).

---

## 1. Widget endpoints — the widget's entire API surface

| # | Method & Path | Auth | Status | Widget support | Notes |
| --- | --- | --- | --- | --- | --- |
| W1 | `POST /api/v1/widget/bootstrap` | `X-Widget-Key` header | `WIDGET-IMPLEMENTED` | `WidgetAuthManager.bootstrap()` → `src/api/WidgetAuth.js` | Returns `{access_token, expires_in, widget_id, configuration{chat, recommendations}}`. Key sent only here; token kept in memory. |
| W2 | `POST /api/v1/widget/chat` | Bearer widget JWT, scope `rag:chat` | `WIDGET-IMPLEMENTED` | `ChatService.sendMessage()` → `src/api/ChatService.js` | Body: `WidgetChatRequestSchema`. **Requires `provider_name` query param** (see §5). Server clamps all AI controls via `apply_widget_policy`. Quota-enforced via `QuotaEnforcer.run`. |
| W3 | `POST /api/v1/widget/recommendations` | Bearer widget JWT, scope `recommendations:read` | `WIDGET-IMPLEMENTED` | `RecommendationService.getRecommendations()` → `src/api/RecommendationService.js` | Body: `WidgetRecommendationRequestSchema {message, customer_id?}`. Quota-enforced. |

**These three endpoints are the complete widget surface.** Everything else below is
admin/SaaS-only or public, and must NOT be called by the widget.

---

## 2. Capabilities requested by the mission — status

| Capability | Endpoint(s) | Widget-callable today? | Status for widget | Evidence |
| --- | --- | --- | --- | --- |
| Chat / RAG answer | `POST /api/v1/widget/chat` | ✅ Yes | `WIDGET-IMPLEMENTED` | router.py `widget_chat`; live 200 test |
| Product recommendations | `POST /api/v1/widget/recommendations` | ✅ Yes | `WIDGET-IMPLEMENTED` | router.py `widget_recommendations` |
| **Ticket creation / lifecycle** | `POST /api/v1/tickets`, `GET/PATCH /api/v1/tickets/{id}`, `.../messages`, `.../resolve`, `.../escalate`, `.../status`, `.../notifications`, `.../metrics/resolution` | ❌ **No — `require_admin_role` at router level** (app/api/ticket/router.py:26) | `CAPABILITY EXISTS BUT: No widget-compatible endpoint currently exists.` | Ticket router has `dependencies=[Depends(require_admin_role)]`; widget tokens have `roles=[]` and never pass `get_current_store_id`. |
| **Escalation to human** | — | ⚠️ **Indirectly**: automatic server-side escalation inside widget chat | `INTEGRATED (server-side only)` | `RagOrchestrationService._check_escalation` (app/application/rag/service.py:317) auto-creates a support ticket when user asks for human + confidence < 0.30 + `customer_id` present + no open ticket. No dedicated widget escalation endpoint — do not invent one. |
| **Bundles** | `POST /api/v1/recommendations/bundle-suggestion`, `GET/PUT /api/v1/admin/bundles/config`, `POST /api/v1/admin/bundles/top/promote`, `DELETE .../top/{bundle_key}`, `POST .../track`, `GET .../tracking...` | ❌ **No — SaaS/admin only** | `CAPABILITY EXISTS BUT: No widget-compatible endpoint currently exists.` | recommendation router uses `get_current_user`; bundle admin routes use `require_admin_role`. |
| **Sales agent / coordinator intents** | (internal workflow, `EXECUTABLE_INTENTS = {bundle, recommendation, sales, support, escalation}`) | ⚠️ Reachable only through `POST /chat` and `POST /api/v1/ai/chat` (SaaS) / RAG paths | `CAPABILITY EXISTS BUT: No widget-compatible endpoint currently exists.` for dedicated sales endpoints; widget chat answers are grounded RAG responses, not coordinator intent routing. | `app/workflows/conversation/graph.py`; widget chat calls `RagOrchestrationService.answer` directly. |
| Knowledge base admin (upload/embed/summaries/search) | `/api/v1/knowledge-base/*`, `/knowledge/*` | ❌ **No — SaaS/admin only** | `CAPABILITY EXISTS BUT: No widget-compatible endpoint currently exists.` | These power the store's KB; the widget only *consumes* answers. |
| Commerce CRUD, inventory, orders, categories | `/api/v1/commerce/*` | ❌ **No — SaaS only** | `CAPABILITY EXISTS BUT: No widget-compatible endpoint currently exists.` | Widget is consumer-facing; commerce admin is SaaS. |
| Integration connections / agent-sync / schema parse | `/api/v1/integration/*` | ❌ **No — SaaS only** | `CAPABILITY EXISTS BUT: No widget-compatible endpoint currently exists.` | |
| Analytics & AI-usage | `/api/v1/analytics/*`, `/api/v1/admin/analytics/*` | ❌ **No — SaaS/admin only** | `CAPABILITY EXISTS BUT: No widget-compatible endpoint currently exists.` | |
| Prompt management | `/api/v1/admin/prompts*` | ❌ **No — admin only** | `CAPABILITY EXISTS BUT: No widget-compatible endpoint currently exists.` | |
| Widget installation admin | `GET/POST /api/v1/admin/widget-installations`, `PATCH .../{widget_id}/disable` | ❌ **No — admin only** (correct: provisioning is admin-only) | `ADMIN-ONLY` (expected) | Used by merchants to obtain `wi_...` keys. |
| Generic LLM chat / stream / structured / tools / embeddings / models / providers | `/chat`, `/api/v1/ai/chat*`, `/api/v1/ai/*` | ❌ **No — SaaS only** | `CAPABILITY EXISTS BUT: No widget-compatible endpoint currently exists.` | Widget chat is the intended consumer path. |
| RAG chat (non-widget) | `/rag/chat`, `/rag/chat/stream` | ❌ **No — SaaS only** | `SAAS-ONLY` | Shares `provider_name` query requirement (see §5). |

---

## 3. Widget token access — what a widget session CAN reach

A valid widget JWT (issuer `AI-Commerce-Widget`) reaches exactly these paths:

- `POST /api/v1/widget/bootstrap` (via key, before token exists)
- `POST /api/v1/widget/chat`
- `POST /api/v1/widget/recommendations`

Widget tokens are rejected by every other path:
- `require_admin_role` → 403 (tickets, widget-installations, bundles config, prompts, admin analytics)
- `get_current_user` / `get_current_store_id` → 401/403 (recommendations, commerce, knowledge-base, integration, analytics, ai, rag, chat)
- `AuthMiddleware._dispatch_widget` never sets `request.state.user`, so SaaS paths cannot pass.

---

## 4. Public paths (no auth)

| Path | Purpose |
| --- | --- |
| `GET /health/` | Health check (live: 200 `{"status":"AI Service is live !"}`) |
| `GET /docs`, `/redoc`, `/openapi.json` | Interactive docs (no auth) |
| `GET /widget.js` | Merchant embed script (live: 200, 52890 bytes, identical to repo bundle) |
| `GET /demo` | Demo storefront page |

---

## 5. Contract notes & divergences (verified live)

1. **`provider_name` query param is REQUIRED** on `POST /api/v1/widget/chat` (and
   `/rag/chat`, `/rag/chat/stream`).
   - Source of truth: it is injected by the dependency chain
     `get_rag_service → get_support_agent → get_escalation_agent → get_provider(provider_name)`
     (`app/api/ai/dependencies.py:100`), NOT declared in the route signature.
   - Verified live: `POST /rag/chat` without `?provider_name=` → **422**
     `{"detail":[{"type":"missing","loc":["query","provider_name"],...}]}`;
     with `?provider_name=openai` → 200.
   - The production OpenAPI and the committed baseline
     (`ai-service/docs/api/openapi-baseline.json`) both declare it required.
   - The widget correctly sends `?provider_name=<config>` (default `openai`) — **no widget change needed**;
     the value is config-only and never consumer-supplied.
2. **Widget request/response schemas** (from `app/api/widget/schemas.py`):
   - `WidgetChatRequestSchema`: `message` (required, 1–4000), `conversation_id?`,
     `customer_id?`, `model?`, `temperature?`, `max_tokens?`, `top_k=5`,
     `score_threshold=0.0`, `use_hybrid=false`, `use_mmr=false`, `rerank=false`,
     `language?`, `knowledge_scope?`.
   - `WidgetChatResponseSchema`: `response`, `citations`, `chunk_references`,
     `confidence_score`, `latency_ms`, `model`, `provider`, `usage`, `business_summary_version`,
     `conversation_id`.
   - `WidgetRecommendationRequestSchema`: `message` (1–2000), `customer_id?`.
   - `WidgetRecommendationResponseSchema`: `query`, `products[]` (product_id, title,
     price, currency, image_url, product_url, specs, match_reasons), `rationale`,
     `total_count`, `latency_ms`, `customer_id`.
   - `WidgetBootstrapResponseSchema`: `access_token`, `expires_in`, `widget_id`,
     `configuration{chat, recommendations}`.
3. **Tenant isolation (server-side):** `get_widget_tenant_context` derives
   `store_id`/`organization_id`/`widget_id` ONLY from validated token claims; any
   client-supplied tenant identifiers are never consulted. Conversation ownership
   is enforced (`conversation_owned_by_store` → 404 on foreign conversation).
4. **Rate limiting:** bootstrap keyed by SHA-256 hash of `X-Widget-Key`
   (R-09 per-key cap); widget chat/recommendations keyed by session `store_id`
   (R-08 per-session cap); LLM tier shared with `/rag/chat`, `/chat`. Static
   `/widget.js` and `/demo` are whitelisted.
5. **CORS:** `WidgetCorsMiddleware` — dynamic origin resolution against active
   installations; never wildcard; exposes `X-RateLimit-*`, `X-Correlation-ID`;
   allows `Authorization`, `Content-Type`, `Accept`, `Origin`, `X-Widget-Key`,
   `X-Correlation-ID`.
6. **No dedicated quota/429 body contract:** widget error handler maps 429 +
   `Retry-After` heuristically (quota/token → quota-exhausted; daily/consumer →
   daily-limit; else generic 429). `Retry-After` is respected by the widget.

---

## 6. Verdict for Phase 1

- **Widget-accessible capabilities: chat (RAG) and recommendations. Both are
  implemented in the current widget bundle and verified compatible with the live
  production contract.**
- Tickets, escalation UI, bundles, sales intents, KB/commerce/integration admin:
  **NOT widget-compatible today** (admin/SaaS-only). Do NOT add widget calls to them.
- Escalation is available **implicitly** through widget chat (server-side auto-ticket
  creation when the customer asks for a human); the widget should surface the
  server's acknowledgment rather than call ticket endpoints.