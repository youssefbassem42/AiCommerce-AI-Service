# AI Commerce Widget — Installation & Integration Guide

> End-to-end reference for installing the storefront AI widget on a merchant
> store: how the widget works, how widget keys are generated, and step-by-step
> integration for **React, Vue, Angular and vanilla JS** stores.
>
> Audience: SaaS backend / .NET service developers (key generation) and
> frontend integration engineers (embed).

**Base URL (production):** `https://aicommerce-ai-service-production.up.railway.app`
**Local:** `http://localhost:8000`
**Embed script:** `GET /widget.js` (served by the AI service itself)
**Demo storefront:** `GET /demo` (loads the real embed script end-to-end)

---

## 1. Architecture — how the widget works

```
Merchant storefront (any framework)
   │  <script src="…/widget.js" data-widget-key="wi_…"></script>
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  widget.js (browser, Shadow DOM, no build step)                  │
│  1. POST /api/v1/widget/bootstrap    (X-Widget-Key: wi_…)       │
│  2. ⇐ access_token (scoped JWT, TTL 15 min) + configuration     │
│  3. POST /api/v1/widget/chat          (Authorization: Bearer)    │
│  4. POST /api/v1/widget/recommendations  (Authorization: Bearer) │
└──────────────────────────────────────────────────────────────────┘
   │                      ▲
   ▼                      │ short-lived scoped JWT
┌─────────────────────────┴───────────────────────────────────────┐
│ AI Service (FastAPI)                                             │
│  AuthMiddleware ── widget issuer → TenantContext resolved        │
│  WidgetCorsMiddleware ── dynamic Origin allow-list from installs │
│  RateLimitMiddleware ── per-key bootstrap / per-session tiers    │
│                                                                  │
│  Bootstrap flow:                                                 │
│   wi_… ──SHA-256──► public_key_hash ──► CachedWidgetOriginService│
│                                        (30 s TTL, invalidated    │
│   hash ──► WidgetInstallation ──► store_id + organization_id     │
│   ──► origin allow-list check ──► scoped session JWT (rag:chat,  │
│                                   recommendations:read)          │
│                                                                  │
│  Widget chat/recommendations are tenant-isolated server-side.    │
│  The browser NEVER sends store_id / organization_id.             │
└──────────────────────────────────────────────────────────────────┘
```

### Key properties

| Property | Value |
|----------|-------|
| Widget key (`wi_…`) | Opaque public credential, shown **once** at creation; only its SHA-256 hash is stored. Replaces the need to ship `store_id`/`organization_id` to the browser. |
| Bootstrap cache | `CachedWidgetOriginService` caches hash → installation in-process (30 s TTL). Disable/edit invalidation happens immediately via `clear()`; otherwise a disabled key is enforced within the TTL. |
| Session token | HMAC-SHA256 JWT, issuer/audience `AI-Commerce-Widget`, default TTL 15 min, carries `widget_id`, `store_id`, `organization_id`, `scopes` — all resolved server-side. |
| Origin policy | If the installation has `allowed_origins`, bootstrap rejects others (generic 401/403). Wildcards are never permitted. Browser CORS for `*` widget paths is served dynamically from active installations. |
| Scope model | `rag:chat` → chat tab; `recommendations:read` → product-finder tab. Requesting a scope the token lacks → 403. |
| Rate limits | 30 bootstrap/min per key hash; 60 session calls/min per store; 20 LLM-generation/min per store; 100 default/min per store. Headers: `X-RateLimit-*`, `Retry-After`. |
| Quota | Every widget chat/recommendation runs through the store's AI quota enforcer (token budget, consumer daily caps). A store without a provisioned plan uses a default policy, never silently unlimited. |

---

## 2. Widget key generation (SaaS admin flow)

Keys are created through the admin API **with the SaaS admin JWT** (issued by
the auth service / .NET backend — same JWT that the dashboard uses). The AI
service takes `store_id` and `organization_id` **from the JWT claims**, never
from the request body.

```http
POST /api/v1/admin/widget-installations
Authorization: Bearer <SaaS-admin-JWT with store_id, organization_id, roles:["admin"]>
Content-Type: application/json

{
  "environment": "live",                        // "live" | "test"
  "allowed_origins": ["https://store.example.com"],   // max 5; empty = no origin check (not recommended for live)
  "scopes": ["rag:chat", "recommendations:read"]
}
```

**Response 201 — the only time the key is ever visible:**

```json
{
  "widget_key": "wi_7f82a91xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "widget_id": "wid_3f0c…",
  "store_id": "store_…",
  "organization_id": "org_…",
  "environment": "live",
  "status": "active",
  "allowed_origins": ["https://store.example.com"],
  "scopes": ["rag:chat", "recommendations:read"]
}
```

> ⚠️ Save `widget_key` immediately — it cannot be retrieved later (only the
> SHA-256 hash is stored). Lost key → disable and create a new installation.

**Management:**

```http
GET   /api/v1/admin/widget-installations                            # list
PATCH /api/v1/admin/widget-installations/{widget_id}/disable        # disable → bootstrap denied within cache TTL
```

Rules enforced server-side: max 5 active installations per store; origins must
be bare `https://host[:port]`; unknown scopes rejected; a disabled
installation immediately stops minting tokens (the 30 s origin cache is
cleared on provisioning changes).

---

## 3. Embed script reference

One `<script>` tag, placed on every storefront page (or only on pages where
the AI assistant should appear):

```html
<script
  src="https://<ai-service>/widget.js"
  data-widget-key="wi_…"
  data-api-base="https://<ai-service>"   <!-- optional: defaults to the script's origin -->
  data-customer-id="ext_cust_123"        <!-- optional: store's external customer id -->
  data-launcher-text="Ask AI"            <!-- optional -->
  data-accent-color="#4f46e5"            <!-- optional -->
></script>
```

### `window.AiCommerceWidget` API

| Member | Purpose |
|--------|---------|
| `init({key, apiBase, customerId, launcherText, accentColor})` | (Re)initialize — updates the data attributes and reloads. |
| `destroy()` | Remove the widget DOM from the page. |
| `current` | The live widget instance (null when not initialized). |

### Behavior contract

- On load the widget calls `POST /api/v1/widget/bootstrap` with
  `X-Widget-Key`. Failure → widget stays hidden and emits a `bootstrap` error
  event; no tenant / key details are exposed in the UI.
- The session JWT lives in memory only (never `localStorage`). Before every
  call the widget re-bootstraps if the token has < 10 s left, and once more
  automatically on a `401`.
- Multi-turn memory: a conversation id is generated and persisted in
  `sessionStorage`, sent as `conversation_id` on every chat call.
- The embed uses a closed Shadow DOM — merchant CSS/JS cannot break or inject
  into the widget, and the merchant's theme cannot be broken by it.
- Progress events (`CustomEvent "ai-commerce-widget"` on `window`):
  `ready`, `chat_started`, `chat_done`, `recommendation_started`,
  `recommendation_done`, `error`, `closed`. The demo page renders these.
- Chat responses render citations; responses with `confidence_score < 0.3`
  append a "contact the store for human support" hint.

---

## 4. Framework-by-framework installation

### 4.1 Vanilla JS (plain HTML / any static site)

1. Copy the `<script>` tag from §3 before `</body>` on every page.
2. Add the page origin(s) to `allowed_origins` at creation time (or re-create
   the installation — origins cannot be edited through the current admin API).

```html
<!-- index.html -->
<script src="https://<ai-service>/widget.js"
        data-widget-key="wi_…">
</script>
```

### 4.2 React (Next.js / CRA / Vite)

Same embed script — managed by a component so it loads once and is unmounted
cleanly (important with hot reload / route changes):

```tsx
// components/AiCommerceWidget.tsx
import { useEffect } from "react";

declare global {
  interface Window {
    AiCommerceWidget?: { init: (o: object) => void; destroy: () => void; current: unknown };
  }
}

const WIDGET_KEY = "wi_…";          // from your backend env/config — NEVER in client git history
const API_BASE = "https://<ai-service>";

export default function AiCommerceWidget() {
  useEffect(() => {
    if (typeof window.AiCommerceWidget === "undefined") {
      const s = document.createElement("script");
      s.src = API_BASE + "/widget.js";
      s.setAttribute("data-widget-key", WIDGET_KEY);
      s.setAttribute("data-api-base", API_BASE);
      document.body.appendChild(s);
      let tries = 0;
      const wait = setInterval(() => {
        if (window.AiCommerceWidget || ++tries > 20) {
          clearInterval(wait);
          window.AiCommerceWidget?.init({ key: WIDGET_KEY, apiBase: API_BASE });
        }
      }, 250);
      return () => {
        clearInterval(wait);
        window.AiCommerceWidget?.destroy();
      };
    }
    window.AiCommerceWidget.init({ key: WIDGET_KEY, apiBase: API_BASE });
    return () => window.AiCommerceWidget?.destroy();
  }, [WIDGET_KEY, API_BASE]);

  return null;
}
```

Mount once in the layout: `<AiCommerceWidget />`.

> For **Next.js**: render in a Client Component (`"use client"`); keep it only
> in the layout, not per-route, or destroy/re-init on navigation. For **SSR**,
> never inline the widget key into server-rendered HTML — fetch it from a
> backend route `/api/widget-config` so the key stays out of pre-rendered
> markup if that matters to your threat model.

### 4.3 Vue 3 (Vite / Nuxt)

```vue
<!-- components/AiCommerceWidget.vue -->
<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";

const WIDGET_KEY = "wi_…";
const API_BASE = "https://<ai-service>";

declare global {
  interface Window {
    AiCommerceWidget?: { init: (o: object) => void; destroy: () => void; current: unknown };
  }
}

onMounted(() => {
  if (typeof window.AiCommerceWidget === "undefined") {
    const s = document.createElement("script");
    s.src = API_BASE + "/widget.js";
    s.setAttribute("data-widget-key", WIDGET_KEY);
    s.setAttribute("data-api-base", API_BASE);
    document.body.appendChild(s);
    const tries: number[] = [];
    const timer = window.setInterval(() => {
      if (window.AiCommerceWidget || tries.length > 20) {
        window.clearInterval(timer);
        window.AiCommerceWidget?.init({ key: WIDGET_KEY, apiBase: API_BASE });
      }
      tries.push(1);
    }, 250);
  } else {
    window.AiCommerceWidget.init({ key: WIDGET_KEY, apiBase: API_BASE });
  }
});

onUnmounted(() => window.AiCommerceWidget?.destroy());
</script>

<template>
  <!-- widget mounts itself; component renders nothing -->
  <span />
</template>
```

Add `<AiCommerceWidget />` once in `App.vue` (or Nuxt `app.vue`). For **Nuxt**
use a client-only wrapper (`<ClientOnly>` or `ssr: false`) since the embed is
DOM/browser-dependent.

### 4.4 Angular (Standalone / NgModule)

```typescript
// ai-commerce-widget.service.ts
declare global {
  interface Window {
    AiCommerceWidget?: { init: (o: object) => void; destroy: () => void; current: unknown };
  }
}

const WIDGET_KEY = "wi_…";
const API_BASE = "https://<ai-service>"; // keep out of public source if possible

export function loadAiCommerceWidget(): void {
  if (typeof window.AiCommerceWidget === "undefined") {
    const s = document.createElement("script");
    s.src = API_BASE + "/widget.js";
    s.setAttribute("data-widget-key", WIDGET_KEY);
    s.setAttribute("data-api-base", API_BASE);
    document.body.appendChild(s);
    let tries = 0;
    const timer = window.setInterval(() => {
      if (window.AiCommerceWidget || ++tries > 20) {
        window.clearInterval(timer);
        window.AiCommerceWidget?.init({ key: WIDGET_KEY, apiBase: API_BASE });
      }
    }, 250);
  } else {
    window.AiCommerceWidget.init({ key: WIDGET_KEY, apiBase: API_BASE });
  }
}

export function destroyAiCommerceWidget(): void {
  window.AiCommerceWidget?.destroy();
}
```

```typescript
// app.component.ts (bootstrap root)
import { Component, OnDestroy, OnInit } from "@angular/core";
import { loadAiCommerceWidget, destroyAiCommerceWidget } from "./ai-commerce-widget.service";

@Component({ selector: "app-root", template: "<router-outlet />" })
export class AppComponent implements OnInit, OnDestroy {
  ngOnInit(): void { loadAiCommerceWidget(); }
  ngOnDestroy(): void { destroyAiCommerceWidget(); }
}
```

> SSR caution (Angular Universal / Analog): guard `loadAiCommerceWidget` with
> `typeof document !== "undefined"` — the embed is browser-only.

---

## 5. End-to-end testing with the demo storefront

The AI service serves a demo storefront at `GET /demo` that runs **the exact
production embed script** (`/widget.js`) — a clean end-to-end check after every
deployment.

**Steps (local):**

1. Start the service locally → `http://localhost:8000`.
2. Create a widget installation with the **demo origin**:

   ```bash
   curl -X POST http://localhost:8000/api/v1/admin/widget-installations \
     -H "Authorization: Bearer <admin-JWT>" \
     -H "Content-Type: application/json" \
     -d '{"environment":"test",
          "allowed_origins":["http://localhost:8000"],
          "scopes":["rag:chat","recommendations:read"]}'
   ```

3. Open `http://localhost:8000/demo?key=wi_…` — the widget loads, bootstraps,
   and you can chat and run the product finder. The panel on the right shows
   every embed event; the Network tab shows the three call types
   (`/bootstrap`, `/chat`, `/recommendations`).
4. **Cache verification:** after provisioning, the origin cache was cleared.
   Disable the installation (`PATCH …/disable`) and re-open the demo → within
   the 30 s cache TTL bootstrap returns the same generic error; disable applies
   immediately for new keys because the cache is invalidated on change.
5. On the **production deployment** the same flow works at
   `https://<railway-host>/demo?key=wi_…` with the Railway origin in
   `allowed_origins`.

---

## 6. Allow-lists, CORS & environment checklist

| Item | Where | Note |
|------|-------|------|
| `allowed_origins` | widget installation (admin API) | Bootstrap rejects other origins with a generic error. Use bare origins (`https://store.example.com`, no trailing slash/path). |
| `data-api-base` | widget script attribute | Must be the AI service origin. Defaults to the script's origin — correct when `/widget.js` is served by the AI service. |
| CORS preflight | `WidgetCorsMiddleware` | Served for `/api/v1/widget/*` from **active installations only** (no wildcard), cached 60 s. A newly created installation may take up to 60 s to be CORS-enabled. |
| SaaS CORS list | `settings.CORS_ORIGINS` | Only relevant for non-widget SaaS paths; the widget path uses the dynamic allow-list above. |
| Auth whitelist | `AuthMiddleware.WHITELIST_PATHS` | `/widget.js` and `/demo` are public static artifacts (`JWT_REQUIRED=true` still applies to all API paths). |
| Cache TTL | `CachedWidgetOriginService` | 30 s in-process per key hash; `clear()` on create/disable. On multi-replica deployments, disabling is enforced within one TTL per replica. |
| Widget token TTL | `WIDGET_TOKEN_TTL_MINUTES` (auth settings) | Default 15 minutes; widget re-bootstraps automatically before expiry. |

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Widget never appears | `data-widget-key` missing/short (< 8 chars); bootstrap rejected (invalid/disabled key) → check admin list; origin not in `allowed_origins`; API base unreachable or wrong port. |
| `401` on chat / recommendations | Session token expired → widget auto-re-bootstraps; if it persists, the installation was disabled mid-session. |
| `403` on a feature tab | Scope not granted on the installation (`scopes` at creation). |
| `429` with `X-RateLimit-Tier: widget_bootstrap` | > 30 bootstraps/min for the key (token refresh storm) — check for loops; the widget only bootstraps on load + near-expiry. |
| `429` widget_session | Store exceeded 60 widget calls/min. |
| CORS blocked in console | Origin not in an **active** installation's `allowed_origins`; newly created installs may need up to 60 s for the CORS cache. |
| Demo shows "widget error: bootstrap" | Key pasted wrong; origin mismatch (demo origin vs `allowed_origins`); service `JWT_REQUIRED=true` does not affect public static assets or bootstrap. |
| Cache: disable not immediate on replica X | In-process cache per replica; worst case one TTL (30 s) per replica. |

---

## 8. Security notes (what to keep in mind)

- The widget key is a **public browser credential** — treat it like a
  public token, not a server secret. It only grants widget-scoped, store-
  scoped, quota-enforced access. Never put cloud/LLM keys or JWT secrets in
  `widget.js` or any embed configuration.
- The browser never supplies `store_id` / `organization_id` — tenant context
  is always resolved server-side from the widget key (bootstrap) and the
  scoped session JWT (chat/recommendations).
- All bootstrap failures return one generic error — a visitor cannot
  distinguish "invalid key" from "disabled installation" from "wrong origin".
- `conversation_id` (session-scoped) and `customer_id` (passed through
  verbatim) never grant cross-tenant access: conversations are ownership-
  checked per store and customer data access stays behind the merchant's own
  authentication.