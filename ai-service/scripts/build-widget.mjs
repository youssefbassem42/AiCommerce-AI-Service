#!/usr/bin/env node
/* Build the AICommerce CDN widget (loader + runtime).
 *
 * Inputs:
 *   app/static/widget/widget.js          - baseline runtime (shipped legacy artifact)
 *   app/static/widget/src/loader.js      - v1 CDN loader source
 *
 * Outputs (committed to the repo; the Docker image serves them statically):
 *   app/static/widget/dist/v1/widget.js          - minified loader (CDN entry)
 *   app/static/widget/dist/v1/runtime.js         - patched + minified runtime
 *   app/static/widget/dist/v1/runtime.<hash>.js  - immutable hashed runtime
 *   app/static/widget/dist/widget.js             - legacy path (patched runtime, self-bootstrap)
 *   app/static/widget/dist/build-manifest.json   - build metadata
 *
 * Every runtime patch is a strict string replacement that HARD FAILS if the
 * needle is not found, so the minified baseline can never drift silently.
 */

import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "app", "static", "widget");
const SRC = join(ROOT, "src");
const DIST = join(ROOT, "dist");
const RUNTIME_VERSION = "v1";

function applyPatches(source, patches) {
  let out = source;
  for (const [name, needle, replacement] of patches) {
    const idx = out.indexOf(needle);
    if (idx === -1) {
      throw new Error(`PATCH FAILED: "${name}" needle not found in runtime`);
    }
    out = out.slice(0, idx) + replacement + out.slice(idx + needle.length);
  }
  return out;
}

const RUNTIME_PATCHES = [
  // P1: apiBaseUrl becomes optional; defaults to the script origin (one-line install).
  [
    "P1-me-api-base-default",
    'function me(i=null){let{script:e}={script:gt(i)},t=e?e.dataset:{},n=(t.widgetKey||Le.widgetKey||"").trim(),s=(t.apiBaseUrl||Le.apiBaseUrl||"").trim(),r=(t.providerName||Me).trim(),a=(t.customerId||"").trim();if(!pe(s)||!s.startsWith("https://")&&!s.startsWith("http://"))throw new Error("ai-commerce-widget: data-api-base-url must be a valid http(s) URL.");',
    'function me(i=null){let{script:e}={script:gt(i)},t=e?e.dataset:{},n=(t.widgetKey||Le.widgetKey||"").trim(),s=(t.apiBaseUrl||Le.apiBaseUrl||"").trim(),r=(t.providerName||Me).trim(),a=(t.customerId||"").trim();if(!s){try{s=e&&e.src?new URL(e.src,window.location.href).origin:""}catch{}}if(s&&(!pe(s)||!s.startsWith("https://")&&!s.startsWith("http://")))throw new Error("ai-commerce-widget: data-api-base-url must be a valid http(s) URL.");',
  ],
  // P2: apiBaseUrl is no longer a hard validation requirement.
  [
    "P2-ge-optional-api-base",
    '(!i.widgetKey||i.widgetKey.length<8)&&e.push("Missing or invalid widget key (data-widget-key)"),i.apiBaseUrl||e.push("Missing API base URL (data-api-base-url)"),',
    '(!i.widgetKey||i.widgetKey.length<8)&&e.push("Missing or invalid widget key (data-widget-key)"),',
  ],
  // P3: conversation persistence — restore from sessionStorage, persist on update/reset.
  [
    "P3-conversation-persistence",
    "var te=class{constructor(){this._conversationId=null,this._startedAt=Date.now()}get id(){return this._conversationId}updateFromResponse(e){typeof e==\"string\"&&e.length>0&&(this._conversationId=e)}reset(){this._conversationId=null,this._startedAt=Date.now()}};",
    "var te=class{constructor(){this._conversationId=null,this._startedAt=Date.now(),this._storageKey=null}get id(){return this._conversationId}setStorageKey(e){this._storageKey=e,this._restore()}setId(e){this._conversationId=e}updateFromResponse(e){typeof e==\"string\"&&e.length>0&&(this._conversationId=e,this._persist())}reset(){this._conversationId=null,this._startedAt=Date.now(),this._persist()}_restore(){if(!this._storageKey)return;try{let e=sessionStorage.getItem(this._storageKey);typeof e==\"string\"&&e.length>0&&(this._conversationId=e)}catch{}}_persist(){if(!this._storageKey)return;try{this._conversationId?sessionStorage.setItem(this._storageKey,this._conversationId):sessionStorage.removeItem(this._storageKey)}catch{}}};",
  ],
  // P4: widget binds its conversation store to a per-key sessionStorage slot.
  [
    "P4-conversation-storage-key",
    "this._conversation=new te,this._messages=[]",
    "this._conversation=new te,this._conversation.setStorageKey(\"ac:conv:\"+String((this.dataset&&this.dataset.widgetKey)||\"\").trim()),this._messages=[]",
  ],
  // P5: consume a loader-provided session before falling back to self-bootstrap.
  [
    "P5-seed-from-slot",
    "this._bootstrapAttempted=!0;try{let e=await this._auth.bootstrap();",
    "this._bootstrapAttempted=!0;try{let e=this._auth.seedFromSlot()||(await this._auth.bootstrap());",
  ],
  // P6: AuthManager gains seedFromSlot(); reuses the bootstrap adapter (q.adapt)
  // so the seeded session has the exact same shape as a live bootstrap response.
  [
    "P6-auth-seed-method",
    "isTokenExpired(){return this._token?this._now()>=this._expiresAt-this.marginSeconds:!0}get expiresInSeconds(){return Math.max(0,this._expiresAt-this._now())}async bootstrap(e={}){",
    "isTokenExpired(){return this._token?this._now()>=this._expiresAt-this.marginSeconds:!0}get expiresInSeconds(){return Math.max(0,this._expiresAt-this._now())}seedFromSlot(){let n=null;try{n=typeof window!=\"undefined\"?window.__AICommerce__:null}catch{return null}if(!n||!n.session)return null;let t=n.session;if(!t||typeof t.access_token!=\"string\"||!t.access_token)return null;let a;try{a=q.adapt(t)}catch{return null}this._token=a.accessToken;let s=this._now();return this._expiresAt=s+a.expiresIn,this._bootstrapError=null,this._bootstrapDone=!0,delete window.__AICommerce__,a}async bootstrap(e={}){",
  ],
  // P8: the panel class never defined focus() although the widget's open()
  // calls this._panel.focus() — open() threw right before bootstrapping, so the
  // session seed was only ever consumed on first send. Give the panel a focus().
  [
    "P8-panel-focus",
    "get lastFocusable(){let e=he(this.element);return e.length>0?e[e.length-1]:null}showWelcome(){",
    "get lastFocusable(){let e=he(this.element);return e.length>0?e[e.length-1]:null}focus(){this.input.focus()}showWelcome(){",
  ],
  // P9: consume the loader-provided session as soon as the widget mounts, so
  // the scoped token lingers in the global slot only for the instant between the
  // loader's stash and runtime execution (not until first open/send).
  [
    "P9-seed-on-mount",
    "this._state.set(h.READY),this._renderLauncher(),this._config.autoOpen&&this.open()",
    "this._state.set(h.READY),this._renderLauncher(),this._ensureApi(),this._auth.seedFromSlot()&&(this._bootstrapAttempted=!0),this._config.autoOpen&&this.open()",
  ],
  // P7 (test-only artifact): export the pure adapter/state classes so Node tests
  // can exercise the exact shipped code. Inert in the browser.
  [
    "P7-test-exports",
    'typeof document!="undefined"&&xt();})();',
    'typeof document!="undefined"&&xt();if(typeof module!="undefined"&&module.exports)module.exports={BootstrapAdapter:q,ChatAdapter:Y,ProductAdapter:U,RecommendationAdapter:Z,Message:E,Conversation:te,MessageValidator:Qe};})();',
  ],
];

const baseline = readFileSync(join(ROOT, "widget.js"), "utf8");
const runtime = applyPatches(baseline, RUNTIME_PATCHES);

mkdirSync(join(DIST, "v1"), { recursive: true });

// Remove stale hashed runtimes from previous builds (only the current hash is
// referenced by the loader; leftovers would grow the bundle over time).
for (const stale of readdirSync(join(DIST, "v1"))) {
  if (/^runtime\.[0-9a-f]{12}\.js$/.test(stale)) {
    rmSync(join(DIST, "v1", stale), { force: true });
  }
}

const runtimeHash = createHash("sha256").update(runtime).digest("hex").slice(0, 12);
const runtimeUrl = `/widget/${RUNTIME_VERSION}/runtime.${runtimeHash}.js`;

await build({
  entryPoints: [join(SRC, "loader.js")],
  bundle: false,
  minify: true,
  target: ["es2017"],
  outfile: join(DIST, "v1", "widget.js"),
  logLevel: "warning",
});

let loader = readFileSync(join(DIST, "v1", "widget.js"), "utf8");
if (!loader.includes("@@RUNTIME_URL@@")) {
  throw new Error("BUILD FAILED: @@RUNTIME_URL@@ placeholder missing from loader bundle");
}
loader = loader.replace("@@RUNTIME_URL@@", runtimeUrl);
writeFileSync(join(DIST, "v1", "widget.js"), loader);

writeFileSync(join(DIST, "v1", "runtime.js"), runtime);
writeFileSync(join(DIST, "v1", `runtime.${runtimeHash}.js`), runtime);
writeFileSync(join(DIST, "widget.js"), runtime);
writeFileSync(join(DIST, "v1", "runtime.test.js"), runtime);

writeFileSync(
  join(DIST, "build-manifest.json"),
  JSON.stringify(
    {
      version: RUNTIME_VERSION,
      runtimeHash,
      runtimeUrl,
      entryUrl: `/${RUNTIME_VERSION}/widget.js`,
      legacyUrl: "/widget.js",
      builtAt: new Date().toISOString(),
      runtimeBytes: runtime.length,
    },
    null,
    2,
  ),
);

console.log(`widget built:
  entry:    ${runtimeUrl.replace(runtimeHash, `<${runtimeHash}>`)}  (loader: dist/v1/widget.js)
  runtime:  dist/v1/runtime.js + dist/v1/runtime.${runtimeHash}.js (${runtime.length} bytes)
  legacy:   dist/widget.js`);