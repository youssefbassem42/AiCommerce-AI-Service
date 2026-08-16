/* Production acceptance test for the CDN widget (spec §43).
 *
 * Loads the one-line install storefront, waits for the widget to mount inside
 * Shadow DOM, sends a discovery question and asserts the STRUCTURED product
 * cards render (the forensic contract), plus fail-safe behavior with an
 * invalid key and session-less widget security.
 *
 * Usage:
 *   E2E_WIDGET_KEY=wi_... node --test tests/widget/e2e-acceptance.test.mjs
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import puppeteer from "puppeteer-core";

const BASE_URL = process.env.E2E_BASE_URL || "https://aicommerce-ai-service-production.up.railway.app";
const WIDGET_KEY = process.env.E2E_WIDGET_KEY || "wi_nZ-s32DtJS1R1F2HrNAtW1DKZpjShmHuAK2D9Ofe5UI";

const LAUNCH = {
  executablePath: "/usr/bin/google-chrome",
  headless: "new",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
};

const WIDGET_SELECTOR = "ai-commerce-widget";

async function openWidget(page) {
  await page.waitForSelector(WIDGET_SELECTOR, { timeout: 20000 });
  const mounted = await page.waitForFunction(
    () => {
      const el = document.querySelector("ai-commerce-widget");
      return el && el.shadowRoot && el.shadowRoot.querySelector("[data-launcher], button[aria-label], .widget-launcher");
    },
    { timeout: 20000 },
  );
  assert.ok(mounted, "widget mounted with a launcher inside shadow DOM");
  return mounted;
}

async function sendMessage(page, message) {
  const launcher = await page.evaluateHandle(() => {
    const el = document.querySelector("ai-commerce-widget");
    return el.shadowRoot.querySelector("[data-launcher], button[aria-label], .widget-launcher");
  });
  await launcher.asElement().click();

  await page.waitForFunction(
    () => {
      const el = document.querySelector("ai-commerce-widget");
      const textarea = el.shadowRoot.querySelector("textarea, input[type='text']");
      return textarea;
    },
    { timeout: 10000 },
  );
  await page.evaluate((msg) => {
    const el = document.querySelector("ai-commerce-widget");
    const textarea = el.shadowRoot.querySelector("textarea, input[type='text']");
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
    setter.call(textarea, msg);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    const sendBtn = [...el.shadowRoot.querySelectorAll("button")].find((b) => /send|➤|→|send/i.test(b.textContent) || b.dataset.send);
    if (sendBtn) sendBtn.click();
    else textarea.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true }));
  }, message);
}

async function countProductCards(page) {
  return page.evaluate(() => {
    const el = document.querySelector("ai-commerce-widget");
    const shadow = el.shadowRoot;
    const cards = shadow.querySelectorAll(".recommendation-card, [class*='product-card'], [class*='ProductCard']");
    return cards.length;
  });
}

test("one-line install: widget mounts and chat returns structured product cards", async () => {
  const browser = await puppeteer.launch(LAUNCH);
  try {
    const page = await browser.newPage();
    const consoleErrors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => consoleErrors.push(err.message));

    await page.goto(`${BASE_URL}/widget/test-store`, { waitUntil: "networkidle2", timeout: 30000 });
    await openWidget(page);

    const statusText = await page.$eval("#widget-state", (el) => el.textContent);
    assert.match(statusText, /bootstrap ok/, `bootstrap status: ${statusText}`);

    await sendMessage(page, "I want a laptop under 3000");
    await page.waitForFunction(
      () => {
        const el = document.querySelector("ai-commerce-widget");
        const shadow = el.shadowRoot;
        const cards = shadow.querySelectorAll(".recommendation-card, [class*='product-card'], [class*='ProductCard']");
        return cards.length > 0;
      },
      { timeout: 90000 },
    );

    const cards = await countProductCards(page);
    assert.ok(cards >= 1, `expected structured product cards, got ${cards}`);

    const firstCardText = await page.evaluate(() => {
      const el = document.querySelector("ai-commerce-widget");
      const card = el.shadowRoot.querySelector(".recommendation-card, [class*='product-card'], [class*='ProductCard']");
      return card ? card.textContent : "";
    });
    assert.ok(firstCardText.length > 0, "product card has content");

    const fatalErrors = consoleErrors.filter((e) => /fatal|uncaught|is not defined/i.test(e));
    assert.equal(fatalErrors.length, 0, `fatal page errors: ${fatalErrors.join("; ")}`);
  } finally {
    await browser.close();
  }
});

test("fail-safe: invalid widget key never breaks the host page", async () => {
  const browser = await puppeteer.launch(LAUNCH);
  try {
    const page = await browser.newPage();
    let pageError = null;
    page.on("pageerror", (err) => (pageError = err.message));
    page.on("dialog", async (d) => d.dismiss());

    await page.goto(`${BASE_URL}/widget/test-store?key=wi_invalidkey1234567890`, {
      waitUntil: "networkidle2",
      timeout: 30000,
    });
    await new Promise((r) => setTimeout(r, 4000));

    const pageStillWorks = await page.evaluate(() => document.title);
    assert.equal(pageStillWorks, "AICommerce Widget — E2E Test Storefront");
    assert.equal(pageError, null, `host page must never see widget errors: ${pageError}`);
  } finally {
    await browser.close();
  }
});

test("session security: widget token is scoped and never leaves the runtime slot", async () => {
  const browser = await puppeteer.launch(LAUNCH);
  try {
    const page = await browser.newPage();
    await page.goto(`${BASE_URL}/widget/test-store`, { waitUntil: "networkidle2", timeout: 30000 });
    await openWidget(page);

    const slotState = await page.evaluate(() => {
      const slot = window.__AICommerce__ || {};
      return {
        hasSession: !!slot.session,
        sessionKeys: slot.session ? Object.keys(slot.session) : [],
        globalKeys: Object.keys(window).filter((k) => /ai|widget/i.test(k)),
      };
    });
    assert.equal(slotState.hasSession, false, "session must be consumed by the runtime (not left in the global slot)");
    assert.ok(!slotState.globalKeys.includes("__AICommerce__"), "global namespace must be minimal");
  } finally {
    await browser.close();
  }
});