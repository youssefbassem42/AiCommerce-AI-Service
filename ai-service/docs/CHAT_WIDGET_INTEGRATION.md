# AI Chat Widget — Frontend Integration Report

> Complete reference for building the AI chat widget against the AI Service.
> Covers: architecture, authentication, headers, every chat/agent/RAG endpoint,
> response bodies, recommended frontend layout per endpoint, and use cases.

**Base URL (production):** `https://aicommerce-ai-service-production.up.railway.app`
**Local:** `http://localhost:8000`
**Interactive docs (OpenAPI):** `GET /docs` (Swagger) · `GET /openapi.json`

---

## 1. Architecture & Business Overview

```
┌──────────────┐   JWT Bearer    ┌───────────────────────────────────────────┐
│ Frontend     │ ───────────────▶│  FastAPI + Middleware (Auth / RateLimit / │
│ Chat Widget  │ ◀───────────────│  Audit / Tracing)                         │
└──────────────┘                 └───────────┬───────────────────────────────┘
                                             │
        ┌───────────────┬────────────────────┼───────────────────────┐
        ▼               ▼                    ▼                       ▼
┌──────────────┐ ┌──────────────┐ ┌───────────────────┐ ┌──────────────────────┐
│  /chat       │ │ /api/v1/ai/  │ │ /rag/chat*        │ │ /api/v1/knowledge-*  │
│  simple      │ │ chat*        │ │ RAG orchestration │ │ KB docs / search /   │
│  LLM chat    │ │ agent chat   │ │ (retrieve+answer) │ │ jobs / summaries     │
└──────────────┘ └──────────────┘ └───────────────────┘ └──────────────────────┘
        │                │                    │
        ▼                ▼                    ▼
  ┌─────────────────────────────────────────────────────┐
  │ Agents (LangGraph, triggered by coordinator)        │
  │ Coordinator → intent routing:                       │
  │   • sales (SalesAgent → products/promo)             │
  │   • bundle (BundleSuggestionService → budget combos)│
  │   • recommendation (spec matching → product cards)  │
  │   • support (SupportAgent → orders/refunds/tickets) │
  │   • escalation (EscalationAgent → human ticket)     │
  │   • general (plain LLM answer)                      │
  ├─────────────────────────────────────────────────────┤
  │ RAG pipeline: RetrieverService (Qdrant vector +     │
  │ keyword hybrid, MMR, rerank) → business summary →   │
  │ LLM answer with [citation:N] markers                │
  ├─────────────────────────────────────────────────────┤
  │ Persistence: MongoDB (conversations, messages,      │
  │ memory, tickets, docs, jobs) · Redis (rate limit)   │
  │ Celery workers (ingestion, embedding, summarization)│
  └─────────────────────────────────────────────────────┘
```

- **Chat widget flow:** the widget sends a message → the API routes it through the
  **Coordinator agent** (decides intent) → the matching **sub-agent** executes with
  store data → the **Memory agent** persists the exchange → response returns with
  `metadata.intent` + `metadata.sub_agent` so the widget can render specialized UI.
- **RAG chat flow:** the message is embedded → vector/hybrid search over the store's
  knowledge base → retrieved chunks + business summary are injected as context →
  LLM answers with `[citation:N]` markers → citations returned in the response.
- **Escalation:** when RAG confidence < 0.30 and the customer asks for a human, the
  service **auto-creates a support ticket** (requires `customer_id` in the request).
- **Conversation memory:** pass a stable `conversation_id` (your own UUID) across
  turns; the service persists history and loads it on every request.

---

## 2. Authentication, Headers & Global Behavior

### 2.1 Authentication model

| Mode | Behavior |
|------|----------|
| `JWT_REQUIRED=true` (production default) | `Authorization: Bearer <JWT>` required on **every** endpoint except `/health/`, `/docs`, `/redoc`, `/openapi.json`. Missing header → `401`. |
| `JWT_REQUIRED=false` (public dev mode) | No header → request passes through as **anonymous** (tenant falls back to body-supplied `store_id`). A **present** token is still always validated. |

**JWT claims consumed by the service:**
| Claim | Used for |
|-------|----------|
| `user_id` | actor id, `customer_id` fallback on AI chat |
| `email` | actor identity |
| `store_id` | tenant isolation, rate-limit key (`store:<store_id>`), automatic filter on knowledge/commerce queries |
| `org_id` (`organization_id`) | org-level filter |
| `roles` (`["admin"]`, `["super_admin"]`, etc.) | endpoint role gates (exact match) |
| `permissions`, `security_stamp`, `jti` | permission checks / token metadata |

### 2.2 Required headers (all chat endpoints)

| Header | Value | Notes |
|--------|-------|-------|
| `Authorization` | `Bearer <JWT>` | required (see 2.1). Send token in every request. |
| `Content-Type` | `application/json` | for JSON bodies; `multipart/form-data` only for document upload |
| `Accept` | `application/json` | for streaming: accept `text/event-stream` |
| `X-Correlation-ID` | optional UUID | echoed back via `Access-Control-Expose-Headers`; used for tracing in logs |
| `Origin` | allowed origin | CORS is enforced — widget must run from one of the allowed origins below |

**Allowed CORS origins (server config):** `http://localhost:3000`, `http://127.0.0.1:3000`,
`https://ai-commerce-frontend-tau.vercel.app`, `https://aicommerce-ai-service-production.up.railway.app`.
> Add your widget's origin to `CORS_ORIGINS` if it is not listed.

### 2.3 Rate limiting

- **Limit:** 100 requests / minute / store (keyed by `store_id` from JWT; falls back to client IP).
- **Response headers on every request:**
  `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (seconds).
- **On exceed:** `429` with `Retry-After` header and body:
  ```json
  { "detail": "Rate limit exceeded. Please try again later.", "limit": 100, "reset_seconds": 43 }
  ```

### 2.4 Error response formats

| Status | Body shape | Example |
|--------|-----------|---------|
| 401 | plain text | `Missing or invalid Authorization header` / `Invalid or expired token` |
| 403 | `{"detail": "..."}` | `Access denied: no roles assigned` (wrong role), `Access denied: no store` (no `store_id` claim) |
| 404 | `{"code": "<ExceptionName>", "message": "...", "details": null}` | domain exceptions (job, document, product, ticket…) |
| 422 | FastAPI validation | `{"detail": [{"type","loc","msg","input"}]}` |
| 429 | `{"detail","limit","reset_seconds"}` | rate limited |
| 500 | `{"code": "internal_error", "message": "Internal server error", "details": null}` | unhandled |

---

## 3. Endpoint Index (chat-widget relevant)

| # | Method & Path | Auth role | Purpose |
|---|---------------|-----------|---------|
| 3.1 | `POST /api/v1/ai/chat` | any user | **Main agent chat** — coordinator + all sub-agents, with conversation memory |
| 3.2 | `POST /api/v1/ai/chat/stream` | any user | Same, **SSE streaming** |
| 3.3 | `POST /api/v1/ai/chat/structured` | any user | LLM output forced to a JSON schema |
| 3.4 | `POST /api/v1/ai/chat/tools` | any user | Chat with function/tool definitions |
| 3.5 | `POST /chat` | any user | **Simple chat** (no agents, no memory) — widget MVP |
| 3.6 | `POST /rag/chat` | any user* | **RAG chat** — answer grounded in the store knowledge base + citations |
| 3.7 | `POST /rag/chat/stream` | any user* | RAG chat, **SSE streaming** (content + final metadata events) |
| 3.8 | `POST /knowledge/retrieval/search` | any user | Standalone semantic retrieval (raw chunks, no LLM) |
| 3.9 | `POST /api/v1/knowledge-base/search` | admin | Same search + store-scoped (KB admin UI / debugging) |
| 3.10 | `POST /api/v1/knowledge-base/search/hybrid` | admin | Hybrid keyword+vector search |
| 3.11 | `POST /api/v1/recommendations/chat` | any user | **Recommendation agent** → structured product cards |
| 3.12 | `POST /api/v1/recommendations/bundle-suggestion` | any user | **Bundle agent** → budget-aware combos + promo code |
| 3.13 | `GET /api/v1/ai/models` | any user | Model list (widget model picker) |
| 3.14 | `GET /api/v1/ai/providers` | any user | Provider + capability list |
| 3.15 | `GET /api/v1/ai/health` | any user | Provider health (status dot) |
| 3.16 | `POST /api/v1/tickets` | admin | Create ticket manually (or rely on auto-escalation) |
| 3.17 | `GET /api/v1/tickets/{ticket_id}/notifications` | admin | Poll ticket notifications after escalation |
| 3.18 | `POST /api/v1/ai/embeddings` | any user | Embed text (advanced widget features) |
| 3.19 | `GET /health/` | none | Service liveness (unauthenticated) |

\* `/rag/*` routers carry no role dependency; with `JWT_REQUIRED=true` they still need a valid Bearer token (tenant is taken from JWT; body `store_id` is the fallback).

---

## 4. Detailed Endpoint Reference

---

### 4.1 `POST /api/v1/ai/chat` — Agent Chat (primary widget endpoint)

- **Use case:** The chat widget's main send-message action. The coordinator agent
  classifies intent and dispatches to the sales / bundle / recommendation / support /
  escalation sub-agents (or a plain LLM answer). Persists the exchange in conversation
  memory. Returns which agent handled the request in `metadata`.

**1) Headers & Auth:**
```
Authorization: Bearer <JWT>          # REQUIRED (any authenticated user)
Content-Type: application/json
```
Optional query param: `?conversation_id=<uuid>` — reuse the same id across turns to keep memory.

**2) Request body:**
```json
{
  "messages": [
    { "role": "user", "content": "I need a gaming laptop under $1500" }
  ],
  "model": "gpt-4o-mini",
  "temperature": 0.7,
  "top_p": null,
  "max_tokens": 1024,
  "stream": false,
  "tools": null,
  "tool_choice": null,
  "json_mode": false
}
```
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `messages[]` | list | yes | roles: `system`, `user`, `assistant`, `developer`, `tool`; `content` string (or vision/tool content list) |
| `model` | string | yes | any model id from `GET /api/v1/ai/models` |
| `temperature` | float 0–2 | no | default provider default |
| `top_p` | float 0–1 | no | |
| `max_tokens` | int | no | |
| `stream` | bool | no | use 4.2 for streaming |
| `tools` / `tool_choice` / `json_mode` | | no | advanced; see 4.3/4.4 |

> A system message is **auto-injected** if absent (e-commerce assistant prompt).

**3) Response body (200):**
```json
{
  "id": "uuid",
  "model": "gpt-4o-mini",
  "provider": "orchestration",
  "message": { "role": "assistant", "content": "Here are 3 laptops that match...",
               "name": null, "tool_call_id": null, "tool_calls": null },
  "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0 },
  "latency_ms": 1234.5,
  "metadata": {
    "intent": "sales",                // bundle | recommendation | sales | support | escalation | general
    "sub_agent": "sales",
    "needs_clarification": false,
    "trace": [ { "step": "coordinator", "intent": "sales", "confidence": 0.91,
                 "sub_agent": "sales", "needs_clarification": false },
               { "step": "execute_agent", "intent": "sales" } ]
  }
}
```
- `metadata.intent` / `metadata.sub_agent` tell the widget which card UI to render.
- When the LLM asks a clarifying question: `needs_clarification: true`, `content` is the question.

**4) Frontend layout:**
- `ChatWidget` — floating button (FAB) → bottom-sheet/panel with:
  message list (user right, bot left), typing indicator while `pending`,
  input bar + send button, error banner (from §2.4), and a small model picker.
- Render `message.content` as markdown.
- If `metadata.intent === "recommendation"` → render product cards;
  `"bundle"` → bundle comparison cards; `"support"` → order/refund status chips;
  `"escalation"` → "A ticket has been created" notice.

---

### 4.2 `POST /api/v1/ai/chat/stream` — Agent Chat (SSE)

- **Use case:** Same as 4.1 but the assistant reply is streamed token-by-token via
  Server-Sent Events for a typing effect. History is still persisted to memory.

**1) Headers & Auth:** same as 4.1 + `Accept: text/event-stream`.
Body: same `ChatRequestSchema` (with `stream` forced true).

**2) Response body (200, `text/event-stream`):** each event is
`data: {json}\n\n` where json is a `StreamingChunkDTO`:
```json
{ "id": "uuid", "model": "gpt-4o-mini", "provider": "openai",
  "content": "Here are", "finish_reason": null, "usage": null }
```
- Concatenate `content` of consecutive events until `finish_reason` is non-null
  (`stop`, `length`, etc.). No final aggregated event is sent.

**3) Frontend layout:** same widget as 4.1 with a `ReadableStream`/`EventSource`-style
parser: append chunks to the last assistant bubble in real time.

---

### 4.3 `POST /api/v1/ai/chat/structured` — Schema-forced output

- **Use case:** Widget features that need guaranteed JSON (e.g., "extract the order
  number from this message") matching a JSON Schema you supply.

**1) Headers & Auth:** Bearer JWT (any user). **2) Request body:**
```json
{ "messages": [{ "role": "user", "content": "Extract: order #1234 was late" }],
  "model": "gpt-4o-mini",
  "schema_definition": { "type": "object",
                         "properties": { "order_id": {"type": "string"} } } }
```
**3) Response:** same `ChatResponseSchema` as 4.1; `message.content` is a JSON string
matching `schema_definition`. **4) Frontend:** parse content with `JSON.parse` and
render a data card; no chat bubbles needed.

---

### 4.4 `POST /api/v1/ai/chat/tools` — Tool-calling chat

- **Use case:** Power users/widget pro mode: pass function definitions so the model can
  request tool calls (returned in `message.tool_calls`); the widget executes and sends
  results back as `role: "tool"` messages.

**1) Headers & Auth:** Bearer JWT. **2) Request body:** `ChatRequestSchema` +
`tools: [{name, description, parameters(json-schema)}]`, `tool_choice`.
**3) Response:** `ChatResponseSchema` — if `message.tool_calls != null`, render
tool-call cards; continue the loop by sending results. **4) Frontend:** `ToolChatView`
with collapsible "Function call" accordions.

---

### 4.5 `POST /chat` — Simple Chat (widget MVP / embedded widget)

- **Use case:** Quickest possible integration: no agents, no memory, no model config.
  Called by the widget when a lightweight answer is enough (e.g., FAQ bot before login).

**1) Headers & Auth:** Bearer JWT (any user).
**2) Request body:**
```json
{ "message": "hello" }
```
**3) Response (200):**
```json
{ "response": "Hi! How can I help you with your store today?" }
```
**4) Frontend layout:** minimal floating widget — FAB + bottom sheet, input + send,
plain text bubbles. No model selector, no citations.

---

### 4.6 `POST /rag/chat` — RAG Chat (knowledge-grounded answers) ★ recommended for chat-with-docs

- **Use case:** THE endpoint for "chatting with your data": retrieves relevant chunks
  from the store knowledge base (vector + optional hybrid/MMR/rerank), attaches the
  store business summary, and produces an answer with clickable citations.
  Auto-escalates to a support ticket when confidence < 0.30 and the user asks for
  human support (requires `customer_id`).

**1) Headers & Auth:**
```
Authorization: Bearer <JWT>        # REQUIRED in production mode
Content-Type: application/json
```
Tenant context: if the JWT has `store_id`/`org_id` claims they **override** the body
values (authoritative). In anonymous mode (public env), the body `store_id` is used.

**2) Request body:**
```json
{
  "message": "What is your return policy for electronics?",
  "conversation_id": "8f3c…uuid…",     // reuse for multi-turn memory
  "store_id": "store_abc123",          // REQUIRED (unless JWT provides it)
  "organization_id": null,
  "customer_id": "cust_42",            // needed for auto-ticket escalation
  "model": null,                        // null → default model
  "temperature": 0.3,
  "max_tokens": 1024,
  "top_k": 5,                           // 1..50 (capped at 10 in context)
  "score_threshold": 0.0,               // 0..1
  "use_hybrid": false,                  // keyword+vector
  "use_mmr": false,
  "rerank": false,
  "language": null,
  "knowledge_scope": null,              // e.g. "general" | "faq" | custom
  "stream": false
}
```
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `message` | string | yes | 1–4000 chars |
| `store_id` | string | yes* | *unless JWT carries it |
| `conversation_id` | string | no | multi-turn memory |
| `customer_id` | string | no | enables auto-ticket on low confidence |
| `top_k` / `score_threshold` / `use_hybrid` / `use_mmr` / `rerank` | | no | retrieval tuning |

**3) Response body (200):**
```json
{
  "response": "Our electronics return policy is 30 days [citation:1][citation:2]. …",
  "citations": [
    { "index": 1, "chunk_id": "ch_…", "document_title": "return-policy.pdf",
      "content_snippet": "Electronics may be returned within 30 days…",
      "score": 0.92, "rank": 1 }
  ],
  "chunk_references": [
    { "chunk_id": "ch_…", "document_id": "doc_…", "document_title": "return-policy.pdf",
      "content_snippet": "…", "score": 0.92, "rank": 1 }
  ],
  "confidence_score": 0.87,
  "latency_ms": 2450.1,
  "model": "gpt-4o-mini",
  "provider": "openai",
  "usage": { "prompt_tokens": 1500, "completion_tokens": 120, "total_tokens": 1620, "cost": 0.0042 },
  "business_summary_version": 3,
  "conversation_id": "8f3c…uuid…"
}
```
- `[citation:N]` markers in `response` map to `citations[].index`.
- `confidence_score` 0–1: <0.3 + human request → ticket auto-created; show a
  "speak to a human / create a ticket" fallback button when score is low.
- If the LLM is rate-limited/unavailable, the service falls back to returning the
  retrieved chunks as plain text with `provider: "fallback"` — render as-is.

**4) Frontend layout:** `RAGChatScreen` — chat bubbles + under each bot message an
expandable **"Sources"** accordion (`citations[]`: title + snippet + score badge),
confidence dot (green ≥0.7 / yellow 0.3–0.7 / red <0.3), and a "Get human help" CTA
that opens the ticket flow.

---

### 4.7 `POST /rag/chat/stream` — RAG Chat (SSE)

- **Use case:** RAG chat with a typing effect. Two event types are sent; the LAST event
  is a `metadata` event carrying citations/confidence — keep it until the stream ends.

**1) Headers & Auth:** same as 4.6 (+ `Accept: text/event-stream`).
**2) Request body:** same as 4.6 (stream flag ignored).

**3) Response (200, `text/event-stream`)** — sequence of `data: {…}\n\n` events:

Content events:
```json
{ "type": "content", "content": "Our policy", "finish_reason": null,
  "citations": [], "chunk_references": [], "confidence_score": null,
  "model": null, "provider": null, "usage": null, "latency_ms": null,
  "business_summary_version": null, "conversation_id": null }
```
Final metadata event (single):
```json
{ "type": "metadata", "content": null, "finish_reason": null,
  "citations": [ { "index": 1, "chunk_id": "ch_…", "document_title": "…",
                   "content_snippet": "…", "score": 0.92, "rank": 1 } ],
  "chunk_references": [ … ],
  "confidence_score": 0.87, "model": "gpt-4o-mini", "provider": "openai",
  "usage": { … }, "latency_ms": 2450.1, "business_summary_version": 3,
  "conversation_id": "8f3c…uuid…" }
```
> Parsing rule: accumulate `content` events; when you receive a `type === "metadata"`
> event, finalize the message (render citations + confidence) and end the stream.
> On LLM failure you still get a content event with `finish_reason: "error"` followed
> by a metadata event with `provider: "fallback"`.

**4) Frontend layout:** same as 4.6, streaming text in the assistant bubble,
sources accordion populated from the final metadata event.

---

### 4.8 `POST /knowledge/retrieval/search` — Standalone Retrieval

- **Use case:** Raw retrieval without generation — used by the widget for
  "related sources" / search-as-you-type suggestions, or by the KB search UI.

**1) Headers & Auth:** Bearer JWT (any user). Tenant taken from JWT `store_id`
(falls back to body `store_id`).

**2) Request body:**
```json
{ "query": "return policy", "top_k": 10, "score_threshold": 0.0,
  "use_hybrid": false, "use_mmr": false, "mmr_lambda": 0.7,
  "rerank": false, "rerank_top_k": 5, "embedding_model": "gemini-embedding-001",
  "organization_id": null, "store_id": null, "language": null,
  "document_type": null, "knowledge_scope": null, "business_version": null }
```
**3) Response (200):**
```json
{ "query": "return policy",
  "results": [ { "chunk_id": "ch_…", "document_id": "doc_…",
                 "document_title": "return-policy.pdf", "chunk_index": 3,
                 "content": "Electronics may be returned within 30 days…",
                 "score": 0.92, "rank": 1,
                 "metadata": { "page": 2 }, "language": "en", "source_type": "pdf" } ],
  "total_count": 4, "strategy": "vector", "latency_ms": 320.4,
  "filters_applied": { "store_id": "store_abc123" } }
```
**4) Frontend layout:** `SourcesPanel` / search results list with relevance bars
(`score`), snippet preview, and document title links.

---

### 4.9 & 4.10 `POST /api/v1/knowledge-base/search` (+`/hybrid`) — Admin KB search

- **Use case:** Same semantics as 4.8 but store-scoped by JWT (`store_id` claim) and
  **admin-only**; useful for KB admin screens and debugging RAG coverage. Hybrid
  version forces keyword+vector (`strategy: "hybrid"`).
- **Auth:** Bearer JWT + `admin` role (403 otherwise). Body = `RetrievalRequestSchema`
  (same fields as 4.8). Response = same `RetrievalResponseSchema`.
- **Frontend:** KB admin search tab; widget should prefer 4.8 / RAG endpoints.

---

### 4.11 `POST /api/v1/recommendations/chat` — Recommendation Agent

- **Use case:** Structured product recommendations with spec matching. Called by the
  widget when the user's message is a product-search request ("show me 4K monitors"),
  or by the coordinator agent internally; the widget can call it directly to render
  rich product cards with match reasons.

**1) Headers & Auth:** Bearer JWT (any user). Tenant: JWT `store_id` wins; else body.

**2) Request body:**
```json
{ "message": "wireless mechanical keyboard under $80", "store_id": "store_abc123",
  "customer_id": "cust_42" }
```
**3) Response (200):**
```json
{ "query": "wireless mechanical keyboard under $80", "store_id": "store_abc123",
  "customer_id": "cust_42",
  "products": [ { "product_id": "p_1", "title": "Keychron K3",
                  "price": "79.00", "currency": "USD",
                  "image_url": "https://…/k3.jpg", "product_url": "https://…/p_1",
                  "specs": [ { "name": "switch", "value": "brown" } ],
                  "match_reasons": ["wireless", "under $80", "mechanical"] } ],
  "rationale": "These match your budget and wireless requirement.",
  "total_count": 3, "latency_ms": 890.2 }
```
**4) Frontend layout:** `ProductCardsGrid` — image, title, price, match-reason badges;
tapping opens `product_url`. Place an "Ask AI" FAB on product listing pages that opens
the widget pre-filled.

---

### 4.12 `POST /api/v1/recommendations/bundle-suggestion` — Bundle Agent

- **Use case:** Budget-aware bundle combos with discounts and a **promo code** the
  customer can copy (e.g., "I have $300 for a desk setup").

**1) Headers & Auth:** Bearer JWT (any user). **2) Request body:** same shape as 4.11.
**3) Response (200):**
```json
{ "query": "…", "store_id": "store_abc123", "customer_id": null,
  "budget": 300.0,
  "bundles": [ { "products": [ { "product_id": "p_1", "product_title": "Monitor",
                  "original_price": "250.00", "discount_pct": 10.0,
                  "discount_amount": "25.00", "price_after_discount": "225.00" } ],
                 "total_original": "350.00", "total_discount": "60.00",
                 "total_after_discount": "290.00", "remaining_budget": 10.0,
                 "within_budget": true, "promo_code": "BUNDLE10", "rank": 1 } ],
  "promo_code": "BUNDLE10", "rationale": "…", "latency_ms": 940.1 }
```
**4) Frontend layout:** side-by-side bundle cards with strikethrough pricing,
discount %, savings, remaining-budget progress bar, and a **Copy promo code** button
(optionally report the copy event to `POST /api/v1/admin/bundles/track`).

---

### 4.13 `GET /api/v1/ai/models` — Model catalog

- **Use case:** Populate the widget's model picker. **Auth:** Bearer JWT.
- **Response (200):** `[{ "name": "gpt-4o-mini", "provider": "openai",
  "capabilities": {"vision":false,"json_mode":true,"tool_calling":true,"streaming":true,"embedding":false},
  "context_length": 128000, "pricing": {...} }]`
- **Frontend:** dropdown; disable models lacking `streaming` when stream mode is on.

### 4.14 `GET /api/v1/ai/providers` — Provider list
- **Use case:** Settings/diagnostics. **Auth:** Bearer JWT.
- **Response (200):** `[{ "provider": "openai", "supported_models": ["gpt-4o-mini", …],
  "capabilities": {"vision":…,"json_mode":…,"tool_calling":…,"streaming":…,"embedding":…} }]`
- **Frontend:** provider cards with green/red status dot (combine with 4.15).

### 4.15 `GET /api/v1/ai/health` — Provider health
- **Use case:** Widget startup check / status dot. **Auth:** Bearer JWT.
- **Response (200):** `{ "status": "healthy", "provider": "openai", "latency_ms": 123.4, "details": null }`
- `GET /health/` (unauthenticated) returns `{ "status": "AI Service is live !" }` for liveness.

### 4.16 `POST /api/v1/tickets` — Create ticket (manual escalation)
- **Use case:** When the user taps "Talk to a human" in the widget (auto-escalation
  only fires on low confidence + explicit phrasing). **Auth:** Bearer JWT + `admin` role.
- **Request body:** `{ "store_id": "…", "customer_id": "…", "conversation_id": "…", "messages": ["…"] }`
- **Response (201):** full `TicketResponseSchema` — `{ id, ticket_id, store_id, customer_id,
  sentiment, category, summary, priority, status, suggested_response, resolution_type,
  analyzed_at, created_at, updated_at, customer, recent_orders, conversation, messages, assigned_to, eta }`
- **Frontend:** after creating, poll 4.17 for agent notifications.

### 4.17 `GET /api/v1/tickets/{ticket_id}/notifications` — Ticket notifications
- **Use case:** Widget polls this to show the human-agent reply / ETA after escalation.
  **Auth:** Bearer JWT + `admin` role.
- **Query:** `?customer_id=&unread_only=&limit=` — **Response (200):**
  `{ "items": [ { "id","ticket_id","store_id","customer_id","message","eta","read","created_at" } ],
     "total": n, "unread": n }`
- **Frontend:** unread badge on the widget bell icon; render `message` + `eta` as a timeline.

### 4.18 `POST /api/v1/ai/embeddings` — Text embeddings
- **Use case:** advanced widget features (semantic search boxes). **Auth:** Bearer JWT.
- **Request:** `{ "input": "text or [texts]", "model": "…" }`
- **Response (200):** `{ "model","provider","embeddings": [[…floats…]], "usage": {…} }`

---

## 5. Recommended Widget Integration Recipe

### 5.1 Happy path (RAG chat widget)

```
1. On widget open:
   GET /api/v1/ai/health  →  show/hide widget status dot
   GET /api/v1/ai/models  →  populate model picker (optional)

2. conversation_id = localStorage.getItem("widget.conversation") || crypto.randomUUID()
   (persist it for the visitor's session — enables multi-turn memory)

3. User sends message  →  POST /rag/chat/stream
   body: { message, conversation_id, store_id, customer_id, top_k: 5, use_hybrid: true }
   → accumulate content events into the assistant bubble
   → on "metadata" event: render citations accordion + confidence dot, stop typing

4. If confidence_score < 0.3 → show "Get human help" button
   On click → POST /api/v1/tickets (admin-scoped) or tell the user a ticket was opened
   → poll GET /api/v1/tickets/{id}/notifications for replies

5. Errors: 401/403 → re-authenticate; 429 → backoff with Retry-After;
   5xx → show generic error + retry button (keep the user's message).
```

### 5.2 Alternative entry points by intent

| User intent | Endpoint | Widget response UI |
|-------------|----------|--------------------|
| General Q&A (no docs needed) | 4.1/4.2 | chat bubbles |
| Chat with store docs / policies | 4.6/4.7 | bubbles + citations |
| "recommend products" | 4.1 (auto) or 4.11 direct | product card grid |
| "build me a bundle" | 4.1 (auto) or 4.12 direct | bundle cards + promo copy |
| "track my order / refund" | 4.1 (support agent) | status chips + ticket CTA |
| "talk to human" | 4.16 + 4.17 | ticket notice + notification poll |
| FAQ-only lightweight widget | 4.5 | plain bubbles |

### 5.3 Conversation lifecycle notes

- `conversation_id` is client-generated (UUID) and **persisted server-side**; history
  is auto-loaded on the next request with the same id. There is no list/delete
  endpoint — drop the id to start a fresh conversation.
- Agent chat (`4.1`) and RAG chat (`4.6`) keep **separate** conversation stores —
  use one endpoint consistently per conversation id.
- Memory agent stores `last_exchange` per conversation and per-customer summaries
  (after 4 messages) to personalize later turns.

### 5.4 Streaming (SSE) parsing contract

- Format: `data: <json>\n\n` per event. Ignore `event:` lines; parse each `data:` line.
- `/api/v1/ai/chat/stream`: all events are content chunks; stop at `finish_reason != null`.
- `/rag/chat/stream`: stop at `type === "metadata"`; that event carries citations,
  `confidence_score`, usage and latency — finalize the bubble with it.
- Keep the fetch/SSE connection alive; server closes after the last event.

---

## 6. Endpoint→File Reference (for developers)

| Endpoint | Source file |
|----------|-------------|
| `/chat` | `app/api/chat/router.py` |
| `/api/v1/ai/*` | `app/api/ai/router.py` |
| `/rag/chat*` | `app/api/rag/router.py` |
| `/knowledge/retrieval/*` | `app/api/knowledge/retrieval_router.py` |
| `/api/v1/knowledge-base/*` | `app/api/knowledge/unified_router.py`, `generation_router.py` |
| `/knowledge/jobs/*` | `app/api/knowledge/job_router.py` |
| `/api/v1/recommendations/*` | `app/api/recommendation/router.py` |
| `/api/v1/tickets/*` | `app/api/ticket/router.py` |
| `/api/v1/commerce/*` | `app/api/commerce/router.py` |
| `/api/v1/integration/*` | `app/api/integration/router.py` |
| `/api/v1/analytics/*`, `/api/v1/admin/*` | `app/api/analytics/router.py`, `app/api/admin/*.py` |
| `/api/v1/auth/*` | `app/api/auth/router.py` |
| Middleware (auth/rate-limit/CORS) | `app/middleware/`, `app/main.py` |
