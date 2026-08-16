import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const SRC = new URL("../../app/static/widget/src/loader.js", import.meta.url).pathname;

function makeElement(tag, attrs = {}) {
  const el = {
    tag,
    attrs: { ...attrs },
    children: [],
    setAttribute(name, value) {
      el.attrs[name] = String(value);
    },
    getAttribute(name) {
      return el.attrs[name] ?? null;
    },
    hasAttribute(name) {
      return name in el.attrs;
    },
    src: attrs.src ?? null,
    get dataset() {
      const out = {};
      for (const [k, v] of Object.entries(el.attrs)) {
        if (k.startsWith("data-")) out[k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = v;
      }
      return out;
    },
    appendChild(child) {
      el.children.push(child);
      return child;
    },
  };
  return el;
}

function setupGlobal(overrides = {}) {
  const head = makeElement("head");
  const scriptTag = overrides.scriptTag ?? makeElement("script", { src: "https://cdn.example/widget/v1/widget.js" });
  const documentMock = {
    currentScript: scriptTag,
    readyState: "complete",
    head,
    body: makeElement("body"),
    getElementsByTagName(tag) {
      return tag === "script" ? [scriptTag] : [];
    },
    createElement(tag) {
      return makeElement(tag);
    },
    addEventListener() {},
  };
  const windowMock = overrides.window ?? {
    location: { href: "https://shop.example.com/" },
    console: { info() {}, debug() {} },
  };
  global.window = windowMock;
  global.document = documentMock;
  global.fetch =
    overrides.fetch ??
    (async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: "tok123",
        expires_in: 3600,
        widget_id: "wid_abc",
        configuration: { chat: true, recommendations: true },
      }),
    }));
  return { windowMock, documentMock, scriptTag };
}

function teardownGlobal() {
  delete global.window;
  delete global.document;
  delete global.fetch;
}

test("loader exposes internals for testing", async () => {
  setupGlobal();
  const L = await import(SRC);
  assert.equal(typeof L.init, "function");
  assert.equal(typeof L.isValidKey, "function");
  assert.equal(typeof L.readConfig, "function");
  assert.equal(typeof L.bootstrap, "function");
  teardownGlobal();
});

test("isValidKey accepts wi_ and wk_live_ keys, rejects garbage", async () => {
  setupGlobal();
  const L = await import(SRC);
  assert.equal(L.isValidKey("wi_v6PgxRI26fmqiZEhcKVQrhDzGIqai5JziH7_oJisQiY"), true);
  assert.equal(L.isValidKey("wk_live_abcdefghijklmnopqrstuvwxyz123456"), true);
  assert.equal(L.isValidKey("short"), false);
  assert.equal(L.isValidKey("wi_"), false);
  assert.equal(L.isValidKey("evil<script>"), false);
  assert.equal(L.isValidKey(""), false);
  assert.equal(L.isValidKey(null), false);
  teardownGlobal();
});

test("readConfig: one-line install resolves API base from script origin", async () => {
  setupGlobal();
  const L = await import(SRC);
  const script = makeElement("script", { src: "https://cdn.example/widget/v1/widget.js" });
  const cfg = L.readConfig(script);
  assert.equal(cfg.widgetKey, "");
  assert.equal(cfg.apiBaseUrl, "https://cdn.example");
  assert.equal(cfg.cdnOrigin, "https://cdn.example");
  teardownGlobal();
});

test("readConfig: data attributes win, apiBaseUrl override respected", async () => {
  setupGlobal();
  const L = await import(SRC);
  const script = makeElement("script", {
    src: "https://cdn.example/widget/v1/widget.js",
    "data-widget-key": "wi_abcdefghijklmnopqrstuvwxyz1234567890ab",
    "data-api-base-url": "https://api.example/",
    "data-position": "left",
    "data-debug": "true",
  });
  const cfg = L.readConfig(script);
  assert.equal(cfg.widgetKey, "wi_abcdefghijklmnopqrstuvwxyz1234567890ab");
  assert.equal(cfg.apiBaseUrl, "https://api.example");
  assert.equal(cfg.cdnOrigin, "https://cdn.example");
  assert.equal(cfg.position, "left");
  assert.equal(cfg.debug, true);
  teardownGlobal();
});

test("bootstrap: success returns session", async () => {
  setupGlobal();
  const L = await import(SRC);
  const cfg = { widgetKey: "wi_abcdefghijklmnopqrstuvwxyz1234567890ab", apiBaseUrl: "https://api.example" };
  const session = await L.bootstrap(cfg);
  assert.equal(session.access_token, "tok123");
  assert.equal(session.expires_in, 3600);
  teardownGlobal();
});

test("bootstrap: non-OK status rejects", async () => {
  setupGlobal({
    fetch: async () => ({ ok: false, status: 401, text: async () => "unauthorized" }),
  });
  const L = await import(SRC);
  const cfg = { widgetKey: "wi_abcdefghijklmnopqrstuvwxyz1234567890ab", apiBaseUrl: "https://api.example" };
  await assert.rejects(() => L.bootstrap(cfg), /bootstrap_status_401/);
  teardownGlobal();
});

test("bootstrap: invalid response shape rejects", async () => {
  setupGlobal({
    fetch: async () => ({ ok: true, status: 200, json: async () => ({ no_token: true }) }),
  });
  const L = await import(SRC);
  const cfg = { widgetKey: "wi_abcdefghijklmnopqrstuvwxyz1234567890ab", apiBaseUrl: "https://api.example" };
  await assert.rejects(() => L.bootstrap(cfg), /bootstrap_invalid_response/);
  teardownGlobal();
});

test("bootstrap: timeout aborts", async () => {
  setupGlobal({
    fetch: async (_url, init) =>
      new Promise((resolve, reject) => {
        init.signal.addEventListener("abort", () => reject(new Error("AbortError")));
      }),
  });
  const L = await import(SRC);
  const cfg = { widgetKey: "wi_abcdefghijklmnopqrstuvwxyz1234567890ab", apiBaseUrl: "https://api.example" };
  await assert.rejects(() => L.bootstrap(cfg), /AbortError/);
  teardownGlobal();
});

test("init: missing key does nothing (no fetch, no injection)", async () => {
  setupGlobal({
    scriptTag: makeElement("script", { src: "https://cdn.example/widget/v1/widget.js" }),
    fetch: async () => {
      throw new Error("fetch must not be called");
    },
  });
  const L = await import(SRC);
  L.init();
  assert.equal(global.window.__AICommerce__, undefined);
  teardownGlobal();
});

test("init: full happy path — session slot, element + runtime injection", async () => {
  const { windowMock, documentMock, scriptTag } = setupGlobal({
    scriptTag: makeElement("script", {
      src: "https://cdn.example/widget/v1/widget.js",
      "data-widget-key": "wi_abcdefghijklmnopqrstuvwxyz1234567890ab",
    }),
  });
  const L = await import(SRC);
  L.init();
  await new Promise((r) => setTimeout(r, 10));

  assert.equal(windowMock.__AICommerce__.session.access_token, "tok123");
  assert.equal(windowMock.__AICommerce__.config.widgetKey, "wi_abcdefghijklmnopqrstuvwxyz1234567890ab");

  const widgetEl = documentMock.body.children.find((c) => c.tag === "ai-commerce-widget");
  assert.ok(widgetEl, "ai-commerce-widget element created");
  assert.equal(widgetEl.attrs["data-widget-key"], "wi_abcdefghijklmnopqrstuvwxyz1234567890ab");
  assert.equal(widgetEl.attrs["data-api-base-url"], "https://cdn.example");

  const runtimeScript = documentMock.head.children.find(
    (c) => c.tag === "script" && c.attrs["data-ai-commerce-runtime"] === "true",
  );
  assert.ok(runtimeScript, "runtime script injected");
  assert.equal(
    runtimeScript.src,
    `https://cdn.example${L.RUNTIME_PATH}`,
    "runtime URL = cdnOrigin + baked RUNTIME_PATH",
  );
  teardownGlobal();
});

test("built dist loader bakes the manifest runtime URL (bake contract)", async () => {
  const manifest = JSON.parse(
    readFileSync(new URL("../../app/static/widget/dist/build-manifest.json", import.meta.url), "utf8"),
  );
  const dist = readFileSync(new URL("../../app/static/widget/dist/v1/widget.js", import.meta.url), "utf8");
  assert.ok(dist.includes(manifest.runtimeUrl), `dist loader must bake ${manifest.runtimeUrl}`);
  assert.ok(!dist.includes("@@RUNTIME_URL@@"), "placeholder must be replaced in the dist build");
});

test("init: bootstrap failure fails safe — no slot, no element, no script", async () => {
  const { windowMock, documentMock } = setupGlobal({
    scriptTag: makeElement("script", {
      src: "https://cdn.example/widget/v1/widget.js",
      "data-widget-key": "wi_abcdefghijklmnopqrstuvwxyz1234567890ab",
    }),
    fetch: async () => ({ ok: false, status: 403, text: async () => "denied" }),
  });
  const L = await import(SRC);
  L.init();
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(windowMock.__AICommerce__, undefined);
  assert.equal(documentMock.body.children.length, 0);
  assert.equal(documentMock.head.children.length, 0);
  teardownGlobal();
});

test("injectRuntime: runtime onerror clears the session slot", async () => {
  const { windowMock, documentMock } = setupGlobal({
    scriptTag: makeElement("script", {
      src: "https://cdn.example/widget/v1/widget.js",
      "data-widget-key": "wi_abcdefghijklmnopqrstuvwxyz1234567890ab",
    }),
  });
  const L = await import(SRC);
  L.init();
  await new Promise((r) => setTimeout(r, 10));
  assert.ok(windowMock.__AICommerce__.session, "session present");

  const runtimeScript = documentMock.head.children.find(
    (c) => c.tag === "script" && c.attrs["data-ai-commerce-runtime"] === "true",
  );
  runtimeScript.onerror();
  assert.equal(windowMock.__AICommerce__.session, undefined, "session cleared after runtime failure");
  teardownGlobal();
});