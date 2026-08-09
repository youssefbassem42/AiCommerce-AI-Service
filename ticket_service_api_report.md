# Ticket Service API Report — AiCommerce AI Service

> **Generated:** 2026-08-09
> **Base URL:** `https://<AI-SERVICE-DOMAIN>`
> **Swagger:** `/docs` · **OpenAPI:** `/openapi.json`

---

## 1. Authentication

| Field | Value |
|---|---|
| Type | JWT Bearer Token |
| Header | `Authorization: Bearer <access_token>` |
| Scope | All paths except `/health`, `/docs`, `/redoc`, `/openapi.json` (`AuthMiddleware` whitelist) |
| Role required | Exact `admin` role claim in the token (`require_admin_role`, contract §6 — `super_admin` does **not** satisfy the `admin` role check) |

**Status codes:**

| Code | Meaning |
|---|---|
| `401` | Missing/invalid token (`detail`: `"Unauthorized"` / `"invalid token format"` style) |
| `403` | Insufficient role — token role ≠ `admin` |
| `404` | Ticket not found → `{"detail": "Ticket '<id>' not found."}` |
| `422` | Pydantic validation error on body/query params |
| `429` | Global rate limit exceeded (`RATE_LIMIT_PER_MINUTE`) |

---

## 2. Ticket Notifications — Real-Time

### 2.1 Current state (pull model)

There is **no push/callback mechanism today**. Notifications are stored server-side by the backend (AI escalation / resolve flows via the ticket service) as Mongo documents, and the client **polls** to retrieve them.

### 2.2 Endpoint — list ticket notifications

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/tickets/{ticket_id}/notifications` |
| **Authenticated** | ✅ Yes — JWT Bearer + `admin` role |
| **Request body** | None (query params only) |

**Path params:**

| Param | Type | Required | Description |
|---|---|---|---|
| `ticket_id` | string | ✅ | ID of the ticket |

**Query params:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `customer_id` | string | ✖️ | — | Filter notifications for one customer |
| `unread_only` | boolean | ✖️ | `false` | Return only unread |
| `limit` | integer | ✖️ | `50` | Max items (min `1`, max `200`) |

**Response — `200 OK`** (`application/json`):

```json
{
  "items": [
    {
      "id": "3f8c1b2a-9d4e-4f7a-8b3c-1a2b3c4d5e6f",
      "ticket_id": "tkt_abc123",
      "store_id": "store_001",
      "customer_id": "cus_xyz789",
      "message": "Your ticket has been escalated. A human agent will follow up within 4 hours.",
      "eta": "2026-08-09T20:00:00Z",
      "read": false,
      "created_at": "2026-08-09T16:00:00Z"
    }
  ],
  "total": 1,
  "unread": 1
}
```

| Field | Type | Description |
|---|---|---|
| `items[].id` | string | UUID v4 of the notification |
| `items[].ticket_id` | string | Owning ticket |
| `items[].store_id` | string | Owning store |
| `items[].customer_id` | string | Target customer (frontend must scope to its customer) |
| `items[].message` | string | Human-readable notification text |
| `items[].eta` | datetime \| null | Expected resolution time (ISO 8601, UTC) |
| `items[].read` | boolean | Default `false` |
| `items[].created_at` | datetime | ISO 8601, UTC |
| `total` | integer | ⚠️ Length of the **current page**, not the DB total |
| `unread` | integer | Unread count for the same filters (computed independently of `limit`) |

**Example:**

```bash
curl -X GET 'https://<AI-SERVICE-DOMAIN>/api/v1/tickets/tkt_abc123/notifications?customer_id=cus_xyz789&unread_only=true&limit=50' \
  -H 'Authorization: Bearer <token>'
```

### 2.2 Making notifications REAL-TIME (recommended approach)

Since a dedicated real-time channel does not exist yet in the backend, below is the contract to align on. The stack already uses **SSE** for chat (`POST /api/v1/ai/chat/stream` returns `text/event-stream`, see `app/api/ai/router.py:69`), so SSE is the natural pattern for notifications.

#### Option A — Polling (works today, zero backend change)

```js
// frontend: poll every 15–30s; keep a ref of the last notification id
async function pollNotifications(ticketId, customerId) {
  const res = await fetch(`/api/v1/tickets/${ticketId}/notifications?customer_id=${customerId}&unread_only=true`);
  const data = await res.json();
  if (data.unread > 0) showBadge(data.unread, data.items);
}
setInterval(() => pollNotifications('tkt_abc123', 'cus_xyz789'), 20000);
```

- Simple, fits the current backend as-is.
- Latency = poll interval; respect the global rate limit.

#### Option B — SSE stream (recommended implementation target)

**Proposed backend endpoint:**

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/v1/tickets/{ticket_id}/notifications/stream` |
| **Authenticated** | ✅ JWT (see auth note below) |
| **Media type** | `text/event-stream` |

**Event payload** (matches `TicketNotificationSchema`):

```json
event: notification
data: {"id":"9f8c...","ticket_id":"tkt_abc123","store_id":"store_001",
       "customer_id":"cus_xyz789","message":"Ticket escalated — agent assigned.",
       "eta":"2026-08-09T20:00:00Z","read":false,"created_at":"2026-08-09T16:00:00Z"}

event: ping
data: {"ts":"2026-08-09T16:05:00Z"}
```

**Frontend consumption** (also covers the auth caveat):

> ⚠️ `EventSource` cannot set the `Authorization` header. Two options:
> 1. Proxy the SSE through the frontend's own API gateway (which injects the JWT), or
> 2. Backend accepts `?access_token=` query param on the stream route and validates it manually with `jwt_validation_service` (same validator `AuthMiddleware` uses).

```js
const es = new EventSource(
  `/api/v1/tickets/${ticketId}/notifications/stream?customer_id=${customerId}`
);
es.addEventListener('notification', (e) => {
  const n = JSON.parse(e.data);
  upsertNotification(n);          // show toast / update badge
  updateUnreadBadge(1);
});
es.addEventListener('ping', () => {/* keepalive; reconnect handled by EventSource */});
```

- Auto-reconnect: EventSource reconnects on drop; on reconnect the client should replay `GET .../notifications?unread_only=true` to catch anything missed between events.
- Recommended: `retry: 3000` (or ACE header), `event: ping` every 15–30s, cache-bust via `Last-Event-ID` for missed-event replay if implemented.

#### Option C — WebSocket

Choose only if the client must also *send* events (e.g. subscription/unsubscription per ticket, presence). For pure server→client notification delivery, SSE (Option B) is simpler and reuses existing infra.

### 2.3 Known limitations & gaps

- ⚠️ **No mark-as-read endpoint exposed** — `TicketNotificationService.mark_read()` / `mark_all_read()` exist in `app.application.ticket.services.notification_service` but are **not wired to any HTTP route**. Frontend currently cannot ack notifications (they stay `unread` forever).
- ⚠️ **No create endpoint** — notifications are produced internally by backend AI flows only.
- ⚠️ **`total` ≠ DB total** — it is `len(items)` of the returned page.
- ⚠️ **Store scoping** — the list endpoint does not enforce `store_id` from the token; frontend must pass `customer_id` explicitly.
- ⚠️ The notifications router is under the `admin`-role router dependency — a **customer-facing** channel would need a separate router/middleware path with customer scope.

---

## 3. Endpoint Scan — Ticket Service (`/api/v1/tickets`)

All endpoints: **authenticated** (JWT + `admin` role) unless stated.

### 3.1 Create ticket

| | |
|---|---|
| **Method/URL** | `POST /api/v1/tickets` |
| **Purpose** | Create ticket; auto-runs sentiment `analysis`, category, summary, priority & suggested response |
| **Status** | `201` |

**Body:**

```json
{
  "store_id": "store_001",
  "customer_id": "cus_xyz789",
  "conversation_id": null,
  "messages": ["Help me with my order"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `store_id` | string | ✅ | |
| `customer_id` | string | ✅ | |
| `conversation_id` | string | ✖️ | |
| `messages` | string[] | ✖️ | max 50 |

**Response:** `TicketResponseSchema` (see §4).

### 3.2 Get ticket

| | |
|---|---|
| **Method/URL** | `GET /api/v1/tickets/{ticket_id}` |
| **Status** | `200` / `404` |
| **Response** | `TicketResponseSchema` |

### 3.3 List tickets

| | |
|---|---|
| **Method/URL** | `GET /api/v1/tickets` |
| **Status** | `200` |
| **Store scope** | From JWT `store_id` claim (`get_current_store_id`) — token must carry it |

**Query params:** `status`, `priority`, `sentiment` (all optional); `page` (≥1, default 1); `page_size` (1–100, default 20).

**Response:** `TicketListResponseSchema` → `{ items: TicketResponseSchema[], total, page, page_size }`.

### 3.4 Resolution metrics

| | |
|---|---|
| **Method/URL** | `GET /api/v1/tickets/metrics/resolution` |
| **Status** | `200` |
| **Response** | `{store_id, total_tickets, ai_resolved, human_resolved, unresolved, escalated, resolution_rate}` |

> Route is declared **before** `/{ticket_id}` so it is not shadowed.

### 3.5 Update status

```
PATCH /api/v1/tickets/{ticket_id}/status   → 200 / 404
```

```json
{ "status": "in_progress", "resolution_type": "ai" }
```

- `status` enum: `open | in_progress | resolved | closed` (required)
- `resolution_type` enum: `ai | human | unresolved | escalated` (optional)

### 3.6 Add message

```
POST /api/v1/tickets/{ticket_id}/messages   → 200 / 404
```

```json
{ "sender": "agent", "content": "We've shipped a replacement." }
```

- `sender` enum: `customer | agent | system` (default `customer`)
- `content`: string, 1–4000 chars

### 3.7 Resolve

```
POST /api/v1/tickets/{ticket_id}/resolve   → 200 / 404
```

```json
{ "resolution_type": "human", "message": "Refunded." }
```

- `resolution_type` enum: `ai | human` (default `human`)
- `message`: optional, ≤4000

### 3.8 Escalate (notification trigger)

```
POST /api/v1/tickets/{ticket_id}/escalate   → 200 / 404
```

```json
{ "priority": "high", "assigned_to": "agent@store.com", "eta": "2026-08-09T20:00:00Z", "message": "VIP customer" }
```

- `priority` enum: `low | medium | high | urgent | p1 | p2 | p3 | p4`
- `assigned_to`: ≤200 chars · `eta`: ISO 8601 · `message`: ≤4000

> This is the flow that generates customer notifications (escalation/resolution paths).

### 3.9 Delete

```
DELETE /api/v1/tickets/{ticket_id}   → 200 {"success": true} / 404
```

---

## 4. `TicketResponseSchema` (shared response model)

| Field | Type | Notes |
|---|---|---|
| `id` | string | |
| `ticket_id` | string | |
| `store_id` | string | |
| `customer_id` | string | |
| `sentiment` | string | e.g. positive/neutral/negative |
| `category` | string | |
| `summary` | string | |
| `priority` | string | |
| `status` | string | |
| `suggested_response` | string | AI-generated |
| `resolution_type` | string | default `unresolved` |
| `analyzed_at` / `created_at` / `updated_at` | datetime | ISO 8601 |
| `customer` | object \| null | `{id, email, first_name, last_name, phone}` |
| `recent_orders` | array | `{id, total_price, currency, financial_status, created_at, line_items[]}` |
| `conversation` | object \| null | `{message_count, last_message_at, recent_messages[]}` |
| `messages` | array | `{id, sender, content, created_at}` |
| `assigned_to` | string \| null | |
| `eta` | datetime \| null | |

---

## 5. Frontend Integration Notes

1. **All ticket + notification calls** need `Authorization: Bearer <token>` with the `admin` role claim and (where noted) a `store_id` claim.
2. **Real-time now:** poll `GET /api/v1/tickets/{ticket_id}/notifications?unread_only=true&limit=<n>` on 15–30s intervals; badge on `unread`.
3. **Real-time later:** switch to SSE stream endpoint (§2.2 Option B) — keep polling as the catch-up/replay mechanism after reconnects.
4. There is **no** customer-facing `/api/v1/notifications` list — only ticket-scoped paths; scope by `customer_id`.
5. Send `X-CorrelationID` header for tracing; responses expose `X-Correlation-ID`, `X-RateLimit-*` headers.
6. Track read state client-side until a mark-as-read endpoint is shipped.