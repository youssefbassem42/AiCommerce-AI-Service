/* AICommerce Widget — CDN Loader (v1)
 *
 * One-line merchant install:
 *   <script src="https://<cdn>/widget/v1/widget.js" data-widget-key="wi_..."></script>
 *
 * Responsibilities (kept intentionally small):
 *   1. Read the Widget Key from the host script tag.
 *   2. Resolve the API origin (data-api-base-url override, else the script origin).
 *   3. POST /api/v1/widget/bootstrap with the key; receive a short-lived JWT + config.
 *   4. Stash the session in a namespaced slot, then lazy-load the Widget Runtime.
 *   5. Fail safe: never throw into the host page, never block rendering.
 *
 * The runtime (loaded on a separate request) consumes the session slot and mounts
 * the <ai-commerce-widget> custom element inside Shadow DOM.
 */
(function () {
  "use strict";

  var SLOT_KEY = "__AICommerce__";
  var RUNTIME_PATH = "@@RUNTIME_URL@@";

  function getScript() {
    if (typeof document === "undefined") return null;
    if (document.currentScript && document.currentScript.src) {
      return document.currentScript;
    }
    var scripts = document.getElementsByTagName("script");
    for (var i = 0; i < scripts.length; i++) {
      var src = scripts[i].getAttribute("src") || "";
      if (src.indexOf("widget.js") !== -1 && scripts[i].hasAttribute("data-widget-key")) {
        return scripts[i];
      }
    }
    for (var j = 0; j < scripts.length; j++) {
      if (scripts[j].hasAttribute("data-widget-key")) return scripts[j];
    }
    return null;
  }

  function readConfig(script) {
    var data = script ? script.dataset : {};
    var key = String(data.widgetKey || "").trim();
    var scriptOrigin = "";
    if (script && script.src) {
      try {
        scriptOrigin = new URL(script.src, window.location.href).origin;
      } catch (e) {
        scriptOrigin = "";
      }
    }
    var apiBase = String(data.apiBaseUrl || "").trim().replace(/\/+$/, "") || scriptOrigin;
    return {
      widgetKey: key,
      apiBaseUrl: apiBase,
      cdnOrigin: scriptOrigin,
      providerName: String(data.providerName || "openai").trim(),
      title: String(data.title || "AI Commerce Assistant").slice(0, 80),
      welcomeMessage: String(
        data.welcomeMessage || "Hi, I can help you with questions about this store. What would you like to know?",
      ).slice(0, 500),
      position: data.position === "left" ? "left" : "right",
      theme: data.theme === "dark" ? "dark" : "light",
      accentColor: /^#[0-9a-fA-F]{3,8}$/.test(String(data.accentColor || "")) ? data.accentColor : null,
      customerId: String(data.customerId || "").trim().slice(0, 256) || null,
      autoOpen: String(data.autoOpen || "") === "true" || String(data.autoOpen || "") === "1",
      debug: String(data.debug || "") === "true" || String(data.debug || "") === "1",
    };
  }

  function isValidKey(key) {
    return typeof key === "string" && /^(wi_|wk_)[A-Za-z0-9_-]{16,}$/.test(key);
  }

  function debugLog(config, message) {
    if (config && config.debug) {
      try {
        console.info("[ai-commerce-widget] " + message);
      } catch (e) {
        /* noop */
      }
    }
  }

  function bootstrap(config) {
    var url = config.apiBaseUrl + "/api/v1/widget/bootstrap";
    var controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = controller
      ? setTimeout(function () {
          controller.abort();
        }, 15000)
      : null;
    var init = {
      method: "POST",
      headers: { Accept: "application/json", "X-Widget-Key": config.widgetKey },
      credentials: "omit",
      cache: "no-store",
    };
    if (controller) init.signal = controller.signal;
    return fetch(url, init)
      .then(function (res) {
        if (!res.ok) {
          return res
            .text()
            .then(function () {
              throw new Error("bootstrap_status_" + res.status);
            })
            .catch(function (err) {
              throw err;
            });
        }
        return res.json();
      })
      .then(function (data) {
        if (!data || typeof data.access_token !== "string" || data.access_token.length === 0) {
          throw new Error("bootstrap_invalid_response");
        }
        return data;
      })
      .finally(function () {
        if (timer) clearTimeout(timer);
      });
  }

  function stashSession(session, config) {
    var slot = {};
    try {
      if (window[SLOT_KEY] && typeof window[SLOT_KEY] === "object") slot = window[SLOT_KEY];
    } catch (e) {
      slot = {};
    }
    slot.session = session;
    slot.config = config;
    try {
      window[SLOT_KEY] = slot;
    } catch (e) {
      /* noop */
    }
  }

  function injectRuntime(config) {
    var runtimeUrl = RUNTIME_PATH;
    if (!/^https?:\/\//.test(runtimeUrl)) {
      runtimeUrl = (config.cdnOrigin || config.apiBaseUrl) + runtimeUrl;
    }
    var el = document.createElement("ai-commerce-widget");
    el.setAttribute("data-widget-key", config.widgetKey);
    el.setAttribute("data-api-base-url", config.apiBaseUrl);
    if (config.providerName) el.setAttribute("data-provider-name", config.providerName);
    if (config.title) el.setAttribute("data-title", config.title);
    if (config.welcomeMessage) el.setAttribute("data-welcome-message", config.welcomeMessage);
    if (config.position) el.setAttribute("data-position", config.position);
    if (config.theme) el.setAttribute("data-theme", config.theme);
    if (config.accentColor) el.setAttribute("data-accent-color", config.accentColor);
    if (config.customerId) el.setAttribute("data-customer-id", config.customerId);
    if (config.autoOpen) el.setAttribute("data-auto-open", "true");
    if (config.debug) el.setAttribute("data-debug", "true");

    var script = document.createElement("script");
    script.src = runtimeUrl;
    script.async = true;
    script.setAttribute("data-ai-commerce-runtime", "true");

    script.onerror = function () {
      try {
        var slot = window[SLOT_KEY];
        if (slot && slot.session) delete slot.session;
      } catch (e) {
        /* noop */
      }
      debugLog(config, "runtime failed to load; widget disabled");
    };

    var head = document.head || document.getElementsByTagName("head")[0];
    var insert = head && head.appendChild ? head : document.body;
    insert.appendChild(script);
    if (document.body) {
      document.body.appendChild(el);
    } else {
      document.addEventListener("DOMContentLoaded", function () {
        document.body.appendChild(el);
      });
    }
  }

  function init() {
    if (typeof window === "undefined" || typeof document === "undefined") return;
    if (window[SLOT_KEY] && window[SLOT_KEY].session) return;
    try {
      var script = getScript();
      var config = readConfig(script);
      if (!isValidKey(config.widgetKey)) {
        debugLog(config, "missing or invalid data-widget-key; skipping");
        return;
      }
      if (!config.apiBaseUrl) {
        debugLog(config, "could not resolve API base URL; skipping");
        return;
      }
      debugLog(config, "bootstrap started");
      bootstrap(config)
        .then(function (session) {
          session.widget_id = session.widget_id || null;
          session.configuration = session.configuration || {};
          stashSession(session, config);
          debugLog(config, "bootstrap ok; loading runtime");
          injectRuntime(config);
        })
        .catch(function (err) {
          debugLog(config, "bootstrap failed: " + (err && err.message ? err.message : "unknown"));
        });
    } catch (err) {
      try {
        if (window.console) window.console.debug("[ai-commerce-widget] init failed:", err);
      } catch (e) {
        /* noop */
      }
    }
  }

  if (typeof window !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
      init();
    }
  }

  // Node test hooks (guarded; inert in the browser bundle).
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      SLOT_KEY,
      RUNTIME_PATH,
      init,
      readConfig,
      isValidKey,
      bootstrap,
      stashSession,
      injectRuntime,
      getScript,
    };
  }
})();