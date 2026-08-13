# AICommerce Widget — Vercel Integration Guide

Deploying the AICommerce floating widget into a site hosted on Vercel
(React/Vite, Angular, or plain static HTML). The widget is a framework-agnostic,
Shadow-DOM-isolated script — integration is always "script tag + one init call",
never a framework component.

## 1. What you integrate

| Artifact | Description |
|---|---|
| `widget.js` (final bundle) | UMD-style IIFE, no dependencies, ~56 KB. Sealed: no `innerHTML`, `eval`, `localStorage`. |
| Global API | `window.AiCommerceWidget` (documented) + `window.AICommerceWidget` (legacy alias): `{ version, init, destroy, mount, getWidget, get current }` |
| Events | `window` `CustomEvent("ai-commerce-widget")` with `detail.status` in `ready` / `chat_started` / `chat_done` / `recommendation_started` / `recommendation_done` / `error` / `closed` |
| Backend | `https://aicommerce-ai-service-production.up.railway.app` (production API on Railway) |

## 2. Host the bundle on your Vercel site (same-origin)

Serving the file from your own origin avoids third-party-script CSP issues and
keeps `script-src 'self'` policy intact.

### Vite / React (AI-Commerce/Front-end)

```bash
mkdir -p public/widget
cp widget/dist/widget.js public/widget/widget.js
```

The file is then served at `https://<your-site>.vercel.app/widget/widget.js`.
Vercel serves everything under `public/` directly — no rewrites or build config
required.

### Angular (17+)

The same file goes into `src/assets/widget/widget.js`. Because `assets` are
copied verbatim, add it to `.gitignore`-friendly copy step or commit the file:

```bash
mkdir -p src/assets/widget
cp widget/dist/widget.js src/assets/widget/widget.js
```

### Static HTML

Drop `widget.js` next to your HTML and reference it relative:
`/widget/widget.js` or `./widget.js`.

## 3. Embed (index.html — any framework)

```html
<script defer src="/widget/widget.js"></script>
```

For Angular use `src/index.html`; for React/Vite `index.html`; for static pages
the page header. `defer` guarantees execution order and non-blocking load.

## 4. Initialize

The widget must only be initialized after the host document is ready. Use the
documented global — it is idempotent (re-calling `init` replaces the previous
instance cleanly), so React 18 `<StrictMode>` double-effects are safe.

### React (App.jsx)

```jsx
import { useEffect } from "react";

export default function App() {
  useEffect(() => {
    window.AiCommerceWidget?.init({
      key: "wi_xxxxxxxxxxxxxxxx",   // your installation key (see §6)
      apiBase: "https://aicommerce-ai-service-production.up.railway.app",
      accentColor: "#4f46e5",
      launcherText: "Ask our AI assistant",
    });
    const onWidgetEvent = (e) => {
      // optional analytics: e.detail.status, e.detail.query, e.detail.count, e.detail.error
    };
    window.addEventListener("ai-commerce-widget", onWidgetEvent);
    return () => window.removeEventListener("ai-commerce-widget", onWidgetEvent);
  }, []);
  // ...
}
```

### Angular (AppComponent)

```ts
import { Component, OnInit, OnDestroy } from "@angular/core";

@Component({ selector: "app-root", template: "<router-outlet />" })
export class AppComponent implements OnInit, OnDestroy {
  private handler = (e: Event) => {
    // optional analytics, e instanceof CustomEvent → e.detail
  };

  ngOnInit(): void {
    window.AiCommerceWidget?.init({
      key: "wi_xxxxxxxxxxxxxxxx",
      apiBase: "https://aicommerce-ai-service-production.up.railway.app",
    });
    window.addEventListener("ai-commerce-widget", this.handler);
  }

  ngOnDestroy(): void {
    window.removeEventListener("ai-commerce-widget", this.handler);
  }
}
```

Angular notes:
- Works with `OnPush` change detection: the widget renders inside its own
  Shadow DOM and communicates via `CustomEvent` on `window` — outside Angular
  change detection, no `zone.js` interaction needed.
- SSR / Angular Universal: only run `init` on the browser. Guard with
  `isPlatformBrowser(platformId)` (or `typeof window !== "undefined"`); the
  widget itself also no-ops when `document` is unavailable.
- Do NOT wrap the widget in an Angular component wrapper — nothing else is
  needed, and wrapping would leak Shadow DOM/CSP isolation.

### Plain HTML page

```html
<script defer src="/widget/widget.js"></script>
<script>
  window.addEventListener("DOMContentLoaded", () => {
    window.AiCommerceWidget.init({
      key: "wi_xxxxxxxxxxxxxxxx",
      apiBase: "https://aicommerce-ai-service-production.up.railway.app",
    });
  });
</script>
```

## 5. Supported init options

| Option | Default | Notes |
|---|---|---|
| `key` | — | Required. Widget installation key, `wi_…`. Missing/invalid → no mount, console error. |
| `apiBase` | — | Required. API origin. |
| `customerId` | `null` | Optional logged-in user id, sent to `/widget/recommendations` only when set. |
| `providerName` | `"openai"` | Backend-controlled query param for chat (`provider_name`); do not change unless the backend supports others. |
| `title` / `welcomeMessage` / `launcherText` | store defaults | UI copy overrides. |
| `position` | `"bottom-right"` | `bottom-right` \| `bottom-left`. |
| `theme` | `"light"` | `light` \| `dark`. |
| `accentColor` | store default | CSS color, e.g. `"#4f46e5"`. |
| `autoOpen` | `false` | Open on mount. |
| `debug` | `false` | Console logging. |

Alternatively the script tag may carry `data-widget-key`, `data-api-base-url`
(and `data-customer-id`, `data-accent-color`, …) attributes; `init` reads those
as defaults.

## 6. Obtaining a widget key

Keys are created server-side (admin-only):

```
POST /api/v1/admin/widget-installations        # with a SaaS admin JWT (Bearer)
# body: {"store_id": "...", "site_url": "https://<your-site>.vercel.app", ...}
# response: {"widget_id": "...", "widget_key": "wi_xxxxxxxxxxxxxxxx", ...}
GET  /api/v1/admin/widget-installations        # list existing installations
PATCH /api/v1/admin/widget-installations/{widget_id}  # disable
```

The key is used only to bootstrap `POST /api/v1/widget/bootstrap` (exchanged
for a short-lived access token, kept in memory, never stored).

## 7. Vercel-specific configuration

`vercel.json` (root of the frontend repo):

```json
{
  "headers": [
    {
      "source": "/widget/widget.js",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=3600" },
        { "key": "X-Content-Type-Options", "value": "nosniff" }
      ]
    }
  ]
}
```

- If you enforce a CSP: keep `script-src 'self'` (the bundle is same-origin).
  If the widget must call the Railway API from the browser, the widget sends
  `X-Widget-Key`/Bearer headers and the backend widget CORS middleware allows
  browser origins for widget endpoints — no `connect-src` change needed unless
  you have a global CSP; if so, add the API origin to `connect-src`.
- No SPA rewrite is needed for `/widget/widget.js`: files under `public/` are
  served before the SPA fallback.

## 8. Deploy & verify

```bash
cd Front-end
npm run build
vercel --prod
```

Then open the deployed URL and check:

1. Launcher (bubble) appears bottom-right with the configured accent color.
2. Console shows no CSP violations; `window.AiCommerceWidget.current` exists.
3. Open the widget, send a message → assistant reply (event
   `chat_started` → `chat_done`).
4. Ask for recommendations → horizontal carousel with product cards (event
   `recommendation_started` → `recommendation_done`, `detail.count` = products).
5. `window.AiCommerceWidget.destroy()` removes the widget and fires `closed`.

A live smoke-test page exists at `demo.html?key=wi_…&api-base=<url>` served by
the backend at `/static/widget/demo.html`.
