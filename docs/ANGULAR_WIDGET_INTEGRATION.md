# AICommerce Widget — Angular + Vercel Integration Guide

Embedding the AICommerce floating widget into an **Angular** application
(Angular 17+, standalone or NgModule) deployed on **Vercel**. The widget is
framework-agnostic and Shadow-DOM-isolated: integration is "script tag in
`src/index.html` + one `init` call", never an Angular component.

## 1. What you integrate

| Artifact | Description |
|---|---|
| `widget.js` (final bundle) | UMD-style IIFE, no dependencies, ~56 KB. Sealed: no `innerHTML`, `eval`, `localStorage`. |
| Global API | `window.AiCommerceWidget` (documented) + `window.AICommerceWidget` (legacy alias): `{ version, init, destroy, mount, getWidget, get current }` |
| Events | `window` `CustomEvent("ai-commerce-widget")`, `detail.status` in `ready` / `chat_started` / `chat_done` / `recommendation_started` / `recommendation_done` / `error` / `closed` |
| Backend | `https://aicommerce-ai-service-production.up.railway.app` (production API on Railway) |

## 2. Host the bundle inside your Angular project (same-origin)

Serving from your own origin keeps `script-src 'self'` CSP intact and avoids
third-party-script rules.

```bash
mkdir -p src/assets/widget
cp widget/dist/widget.js src/assets/widget/widget.js
```

`src/assets/**` is copied verbatim by the Angular build. The file is served at:

```
https://<your-site>.vercel.app/widget/widget.js
```

(If your `angular.json` sets a custom `assetConfig` or `outputPath`, adjust —
`assets` are copied as-is either way.)

## 3. Embed — `src/index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>My Store</title>
    <base href="/" />
    <script defer src="/widget/widget.js"></script>
  </head>
  <body>
    <app-root></app-root>
  </body>
</html>
```

`defer` guarantees the script runs after parsing, non-blocking. Because the
widget initializes on its own data attributes or via `init()`, the script tag
alone does nothing until you call `window.AiCommerceWidget.init(...)` — so the
page renders instantly and the launcher appears after `init`.

## 4. Initialize — AppComponent

The widget must be initialized only after the document is ready and only on the
browser (SSR guard). `init` is idempotent: calling it again replaces the
previous instance cleanly, so Angular zone re-runs / hot reload are safe.

### Standalone component (Angular 17+)

`src/app/app.component.ts`:

```ts
import { Component, OnInit, OnDestroy, Inject, PLATFORM_ID } from "@angular/core";
import { isPlatformBrowser } from "@angular/common";

@Component({
  selector: "app-root",
  standalone: true,
  imports: [],
  template: `<router-outlet />`,
})
export class AppComponent implements OnInit, OnDestroy {
  constructor(@Inject(PLATFORM_ID) private platformId: object) {}

  private handler = (e: Event): void => {
    const detail = (e as CustomEvent).detail; // { status, query?, count?, error? }
    if (detail?.status === "chat_done") {
      console.log("chat finished for:", detail.query);
    }
  };

  ngOnInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    (window as any).AiCommerceWidget?.init({
      key: "wi_xxxxxxxxxxxxxxxx", // your installation key (see §7)
      apiBase: "https://aicommerce-ai-service-production.up.railway.app",
      accentColor: "#4f46e5",
      launcherText: "Ask our AI assistant",
    });
    window.addEventListener("ai-commerce-widget", this.handler);
  }

  ngOnDestroy(): void {
    window.removeEventListener("ai-commerce-widget", this.handler);
  }
}
```

### NgModule app (Angular < 17, same pattern)

`src/app/app.component.ts` — same class body; `templateUrl`/`styleUrls` as
usual. No module registration is needed for the widget itself; only the
`<script>` tag in `index.html` matters.

## 5. Angular-specific notes

- **Change detection (`OnPush`):** the widget renders in its own Shadow DOM and
  talks to the host only via `CustomEvent` on `window`. It never touches Angular
  state, so `OnPush` components are unaffected — no `ChangeDetectorRef` calls,
  no `NgZone` involvement required.
- **SSR / Angular Universal:** guard `init` with `isPlatformBrowser`. On the
  server the widget no-ops anyway (`document` unavailable), but the guard keeps
  your server bundle clean.
- **Do not create an Angular wrapper component.** Wrapping the widget in a
  component adds nothing and can break Shadow DOM/CSP isolation. Use the script
  tag + `init` as documented.
- **StrictMode / HMR:** `init` replaces any existing instance, so double
  initialization during dev/HMR is safe and leaves exactly one launcher.
- **TypeScript:** the widget is not a typed npm package; declare it once:

  ```ts
  declare global {
    interface Window {
      AiCommerceWidget?: {
        init: (opts: Record<string, unknown>) => HTMLElement | null;
        destroy: () => boolean;
        current: HTMLElement | null;
        version: string;
      };
    }
  }
  ```

## 6. Supported init options

| Option | Default | Notes |
|---|---|---|
| `key` | — | Required. Installation key, `wi_…`. Missing/invalid → no mount. |
| `apiBase` | — | Required. API origin (production Railway URL). |
| `customerId` | `null` | Optional logged-in user id; sent to `/widget/recommendations` only when set (e.g. `this.authService.userId`). |
| `providerName` | `"openai"` | Backend-controlled `provider_name` query param for chat; keep default unless the backend supports others. |
| `title` / `welcomeMessage` / `launcherText` | store defaults | UI copy overrides. |
| `position` | `"bottom-right"` | `bottom-right` \| `bottom-left`. |
| `theme` | `"light"` | `light` \| `dark`. |
| `accentColor` | store default | CSS color, e.g. `"#4f46e5"`. |
| `autoOpen` | `false` | Open on mount. |
| `debug` | `false` | Console logging. |

Alternative: `data-widget-key`, `data-api-base-url` (and `data-customer-id`,
`data-accent-color`, …) attributes on the script tag — `init` reads those as
defaults, so passing nothing works too.

## 7. Obtaining a widget key

Keys are created server-side (admin-only):

```
POST /api/v1/admin/widget-installations        # Bearer: SaaS admin JWT
# body: {"store_id": "...", "site_url": "https://<your-site>.vercel.app", ...}
# response: {"widget_id": "...", "widget_key": "wi_xxxxxxxxxxxxxxxx", ...}
GET  /api/v1/admin/widget-installations        # list existing installations
PATCH /api/v1/admin/widget-installations/{widget_id}  # disable
```

The key is used only to bootstrap `POST /api/v1/widget/bootstrap` (exchanged
for a short-lived access token, kept in memory, never stored).

## 8. Vercel-specific configuration

`vercel.json` at the repo root:

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

- CSP: keep `script-src 'self'` (bundle is same-origin). The widget sends
  `X-Widget-Key`/Bearer headers; backend widget CORS allows browser origins for
  widget endpoints. Only if you enforce a strict global CSP, add the API origin
  to `connect-src`.
- Files in `src/assets/` are emitted to the output root, so
  `/widget/widget.js` is served before the SPA fallback — no rewrite needed.
- `browser` output (default) vs `server`: assets are emitted for both; no
  `angular.json` change required.

## 9. Deploy & verify

```bash
ng build
vercel --prod
```

Checklist on the deployed URL:

1. Launcher bubble appears (configured accent color, position).
2. DevTools: no CSP violations; `window.AiCommerceWidget.current` is set.
3. Send a message → assistant reply (`chat_started` → `chat_done` events).
4. Ask for recommendations → horizontal carousel with product cards
   (`recommendation_started` → `recommendation_done`, `detail.count` = items).
5. `window.AiCommerceWidget.destroy()` removes the widget, fires `closed`.

Live smoke-test page served by the backend:
`https://aicommerce-ai-service-production.up.railway.app/static/widget/demo.html?key=wi_…&api-base=<url>`