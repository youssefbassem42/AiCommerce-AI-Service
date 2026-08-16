import { test } from "node:test";
import assert from "node:assert/strict";

const RUNTIME = new URL("../../app/static/widget/dist/v1/runtime.test.js", import.meta.url).pathname;

// The runtime defines a custom element class at load time; Node has no DOM, so
// provide a minimal HTMLElement base. Only the class *definition* needs it.
if (typeof globalThis.HTMLElement === "undefined") {
  globalThis.HTMLElement = class HTMLElement {
    constructor() {}
    attachShadow() {
      return {};
    }
  };
}

const R = await import(RUNTIME);

const realSessionStorage = globalThis.sessionStorage;

test("runtime exports the adapters/state classes (test artifact)", () => {
  for (const key of [
    "BootstrapAdapter",
    "ChatAdapter",
    "ProductAdapter",
    "RecommendationAdapter",
    "Message",
    "Conversation",
    "MessageValidator",
  ]) {
    assert.ok(R[key], `runtime must export ${key}`);
  }
});

test("BootstrapAdapter.adapt maps access_token/expires_in/widget_id/configuration", () => {
  const out = R.BootstrapAdapter.adapt({
    access_token: "jwt-token",
    expires_in: 3600,
    widget_id: "wid_123",
    configuration: { chat: true, recommendations: false },
  });
  assert.deepEqual(out, {
    accessToken: "jwt-token",
    expiresIn: 3600,
    widgetId: "wid_123",
    configuration: { chat: true, recommendations: false },
  });
});

test("BootstrapAdapter.adapt rejects malformed responses", () => {
  assert.throws(() => R.BootstrapAdapter.adapt(null));
  assert.throws(() => R.BootstrapAdapter.adapt("nope"));
  assert.throws(() => R.BootstrapAdapter.adapt({}));
  assert.throws(() => R.BootstrapAdapter.adapt({ access_token: "", expires_in: 3600, widget_id: "x" }));
  assert.throws(() => R.BootstrapAdapter.adapt({ access_token: "t", expires_in: 0, widget_id: "x" }));
});

test("ChatAdapter.adapt keeps structured fields (the forensic contract)", () => {
  const out = R.ChatAdapter.adapt({
    response: "Here are some products.",
    type: "products",
    citations: [{ index: 0, chunk_id: "c1", document_title: "Catalog", content_snippet: "src", score: 0.9, rank: 1 }],
    products: [
      {
        product_id: "p1",
        title: "Laptop",
        price: "1200.00",
        original_price: "1500.00",
        currency: "USD",
        image_url: "https://img.example/p1.jpg",
        product_url: null,
        match_reasons: ["budget", "type"],
      },
    ],
    product: null,
    bundle: null,
    reference: "https://docs.example",
    conversation_id: "conv_42",
    confidence_score: 0.87,
  });
  assert.equal(out.type, "recommendation");
  assert.equal(out.content, "Here are some products.");
  assert.equal(out.conversationId, "conv_42");
  assert.equal(out.confidenceScore, 0.87);
  assert.equal(out.citations.length, 1);
  assert.equal(out.products.length, 1);
  assert.equal(out.products[0].id, "p1");
  assert.equal(out.products[0].title, "Laptop");
  assert.equal(out.products[0].price, "1200.00");
  assert.equal(out.products[0].currency, "USD");
  assert.equal(out.products[0].productUrl, null);
  assert.deepEqual(out.products[0].matchReasons, ["budget", "type"]);
  assert.equal(out.bundle, null);
  assert.equal(out.product, null);
  assert.ok(out.reference);
});

test("ChatAdapter.adapt maps every backend type via the type table", () => {
  const cases = [
    { in: "text", out: "text" },
    { in: "products", out: "recommendation" },
    { in: "product_detail", out: "product" },
    { in: "bundle", out: "bundle" },
    { in: "escalation", out: "escalation" },
    { in: "ticket_created", out: "text" },
    { in: "error", out: "text" },
  ];
  for (const c of cases) {
    const out = R.ChatAdapter.adapt({ response: "x", type: c.in, conversation_id: null });
    assert.equal(out.type, c.out, `type ${c.in} -> ${c.out}`);
  }
});

test("ChatAdapter.adapt: product_detail fills the product field", () => {
  const out = R.ChatAdapter.adapt({
    response: "This is the one.",
    type: "product_detail",
    product: { product_id: "p9", title: "Wireless Earbuds", price: "99.0", currency: "USD", image_url: null },
  });
  assert.equal(out.type, "product");
  assert.equal(out.product.id, "p9");
  assert.equal(out.product.title, "Wireless Earbuds");
  assert.equal(out.products.length, 0);
});

test("ChatAdapter.adapt: bundle fills the bundle field", () => {
  const out = R.ChatAdapter.adapt({
    response: "Grab both.",
    type: "bundle",
    bundle: { title: "Starter Bundle", items: [{ product_id: "a", title: "A", price: "1", currency: "USD" }], total: 2 },
  });
  assert.equal(out.type, "bundle");
  assert.equal(out.bundle.items.length, 1);
  assert.equal(out.bundle.items[0].id, "a");
  assert.equal(out.bundle.items[0].title, "A");
});

test("Message carries the full structured payload (forensic regression)", () => {
  const msg = new R.Message({
    role: "assistant",
    content: "look",
    citations: [],
    recommendations: [{ id: "r1", title: "T" }],
    type: "recommendation",
    products: [{ id: "p1", title: "Laptop", price: 1200, currency: "USD" }],
    product: null,
    bundle: null,
    reference: null,
  });
  assert.equal(msg.type, "recommendation");
  assert.equal(msg.content, "look");
  assert.equal(msg.recommendations.length, 1);
  assert.equal(msg.products.length, 1);
  assert.equal(msg.products[0].id, "p1");
});

test("ProductAdapter tolerates missing optional fields", () => {
  const out = R.ProductAdapter({
    product_id: "x1",
    title: "Widget",
    price: "55.0",
    currency: "USD",
  });
  assert.equal(out.id, "x1");
  assert.equal(out.title, "Widget");
  assert.equal(out.imageUrl, null);
  assert.equal(out.productUrl, null);
  assert.equal(out.rating, null);
  assert.equal(out.inStock, null);
});

test("RecommendationAdapter.adapt maps the recommendations payload", () => {
  const out = R.RecommendationAdapter.adapt({
    query: "laptop",
    products: [{ product_id: "a", title: "A", price: "1", currency: "USD" }],
    total_count: 1,
    rationale: "because",
  });
  assert.equal(out.type, "recommendation");
  assert.equal(out.query, "laptop");
  assert.equal(out.rationale, "because");
  assert.equal(out.totalCount, 1);
  assert.equal(out.products.length, 1);
});

test("Conversation persists conversation_id to sessionStorage and restores it", async () => {
  const storage = new Map();
  globalThis.sessionStorage = {
    getItem: (k) => (storage.has(k) ? storage.get(k) : null),
    setItem: (k, v) => storage.set(k, v),
    removeItem: (k) => storage.delete(k),
  };
  try {
    const conv = new R.Conversation();
    assert.equal(conv.id, null);
    conv.setStorageKey("ac:conv:wi_testkey");
    conv.updateFromResponse("conv_99");
    assert.equal(conv.id, "conv_99");
    assert.equal(storage.get("ac:conv:wi_testkey"), "conv_99");

    const restored = new R.Conversation();
    restored.setStorageKey("ac:conv:wi_testkey");
    assert.equal(restored.id, "conv_99", "conversation restored across widget instances");

    restored.reset();
    assert.equal(restored.id, null);
    assert.equal(storage.has("ac:conv:wi_testkey"), false, "reset clears storage");
  } finally {
    if (realSessionStorage !== undefined) globalThis.sessionStorage = realSessionStorage;
    else delete globalThis.sessionStorage;
  }
});

test("MessageValidator rejects empty and over-long messages", () => {
  assert.equal(R.MessageValidator("").valid, false);
  assert.equal(R.MessageValidator("   ").valid, false);
  assert.equal(R.MessageValidator("hello").valid, true);
  assert.equal(R.MessageValidator("x".repeat(2049)).valid, true, "up to 4000 chars is valid (backend limit)");
  assert.equal(R.MessageValidator("x".repeat(4001)).valid, false);
});