/*
 * AI Commerce Widget - client-side embed script.
 *
 * Install on any storefront with a single script tag:
 *
 *   <script
 *     src="https://<ai-service-host>/widget.js"
 *     data-widget-key="wi_..."
 *     data-api-base="https://<ai-service-host>"      (optional, defaults to script origin)
 *     data-customer-id="ext_cust_123"                (optional, passed through to the API)
 *     data-launcher-text="Ask AI"                    (optional)
 *     data-accent-color="#5b21b6"                    (optional)
 *   ></script>
 *
 * Flow (see WIDGET_INSTALLATION_GUIDE.md):
 *   1. POST /api/v1/widget/bootstrap with X-Widget-Key -> scoped session JWT + configuration.
 *   2. Chat requests:      POST /api/v1/widget/chat           (Bearer widget JWT)
 *   3. Recommendations:    POST /api/v1/widget/recommendations (Bearer widget JWT)
 *
 * The widget never sees or sends tenant identifiers (store_id / organization_id);
 * the service resolves them server-side from the widget key. The session token is
 * short-lived; the widget re-bootstraps automatically before expiry and once on 401.
 *
 * The script is framework-agnostic (vanilla JS, no build step) and self-contained:
 * it renders into a closed Shadow DOM so merchant CSS/JS cannot break it.
 */

(function () {
  "use strict";

  var VERSION = "1.0.0";
  var EVENT_NAME = "ai-commerce-widget";

  var DEFAULT_TITLE = "AI Assistant";
  var TOKEN_REFRESH_LEAD_SECONDS = 10;
  var CONVERSATION_STORAGE_KEY = "aicommerce_widget_conversation_id";

  function lastScript() {
    var scripts = document.querySelectorAll("script[data-widget-key]");
    return scripts.length ? scripts[scripts.length - 1] : null;
  }

  function readConfig() {
    var el = lastScript();
    var origin = (window.location.origin || "").replace(/\/$/, "");
    return {
      widgetKey: el ? el.getAttribute("data-widget-key") : "",
      apiBase: (el && el.getAttribute("data-api-base")) || origin,
      customerId: el ? el.getAttribute("data-customer-id") || "" : "",
      launcherText: el ? el.getAttribute("data-launcher-text") || DEFAULT_TITLE : DEFAULT_TITLE,
      accentColor: el ? el.getAttribute("data-accent-color") || "#4f46e5" : "#4f46e5",
    };
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  /* Lightweight markdown-ish formatting: paragraphs, bold, italic, links. */
  function formatText(text) {
    var escaped = escapeHtml(text);
    return escaped
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(
        /((?:https?:\/\/|www\.)[^\s<]+)/g,
        '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
      )
      .replace(/\n/g, "<br>");
  }

  var STYLES = [
    "* { box-sizing: border-box; margin: 0; padding: 0; }",
    ".aew-root { position: fixed; z-index: 2147483000; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }",
    ".aew-root.aew-bottom-right { bottom: 18px; right: 18px; }",
    ".aew-fab { width: 56px; height: 56px; border-radius: 50%; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 14px rgba(0,0,0,.25); transition: transform .15s ease; }",
    ".aew-fab:hover { transform: scale(1.06); }",
    ".aew-fab svg { width: 26px; height: 26px; fill: #fff; }",
    ".aew-panel { position: fixed; z-index: 2147483001; width: 380px; max-width: calc(100vw - 24px); height: 560px; max-height: calc(100vh - 24px); border-radius: 14px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 12px 40px rgba(0,0,0,.3); background: #fff; color: #1f2937; font-size: 14px; border: 1px solid #e5e7eb; }",
    ".aew-panel.aew-bottom-right { bottom: 18px; right: 18px; }",
    ".aew-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; color: #fff; }",
    ".aew-header-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }",
    ".aew-header-title svg { width: 18px; height: 18px; fill: #fff; }",
    ".aew-close { background: transparent; border: none; color: #fff; font-size: 18px; cursor: pointer; line-height: 1; opacity: .85; }",
    ".aew-close:hover { opacity: 1; }",
    ".aew-tabs { display: flex; background: #f3f4f6; border-bottom: 1px solid #e5e7eb; }",
    ".aew-tab { flex: 1; padding: 8px 0; text-align: center; background: transparent; border: none; cursor: pointer; color: #6b7280; font-size: 13px; font-weight: 500; border-bottom: 2px solid transparent; }",
    ".aew-tab.aew-active { color: inherit; border-bottom-color: currentColor; }",
    ".aew-messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; background: #fafafa; }",
    ".aew-msg { max-width: 85%; padding: 9px 12px; border-radius: 12px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }",
    ".aew-msg-user { align-self: flex-end; color: #fff; border-bottom-right-radius: 3px; }",
    ".aew-msg-bot { align-self: flex-start; background: #fff; border: 1px solid #e5e7eb; border-bottom-left-radius: 3px; }",
    ".aew-msg-error { align-self: center; background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; font-size: 12px; }",
    ".aew-msg a { color: inherit; text-decoration: underline; }",
    ".aew-typing { display: inline-flex; gap: 4px; padding: 10px 12px; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; border-bottom-left-radius: 3px; align-self: flex-start; }",
    ".aew-typing i { width: 6px; height: 6px; border-radius: 50%; background: #9ca3af; animation: aew-blink 1.2s infinite; }",
    ".aew-typing i:nth-child(2) { animation-delay: .2s; }",
    ".aew-typing i:nth-child(3) { animation-delay: .4s; }",
    "@keyframes aew-blink { 0%,80%,100% { opacity: .25; } 40% { opacity: 1; } }",
    ".aew-sources { align-self: flex-start; width: 100%; margin-top: 2px; }",
    ".aew-sources-toggle { background: none; border: none; color: #6b7280; font-size: 12px; cursor: pointer; text-decoration: underline; padding: 2px 0; }",
    ".aew-sources-list { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px 10px; font-size: 12px; color: #4b5563; margin-top: 4px; }",
    ".aew-sources-list li { margin: 4px 0 4px 16px; }",
    ".aew-products { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; }",
    ".aew-product { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 8px; display: flex; flex-direction: column; gap: 4px; }",
    ".aew-product img { width: 100%; height: 70px; object-fit: contain; border-radius: 6px; background: #f9fafb; }",
    ".aew-product-title { font-size: 12px; font-weight: 500; line-height: 1.3; }",
    ".aew-product-price { font-size: 13px; font-weight: 700; }",
    ".aew-product-link { font-size: 11px; color: inherit; text-decoration: none; text-align: center; padding: 4px 0; border-radius: 6px; color: #fff; }",
    ".aew-reasons { font-size: 10px; color: #6b7280; }",
    ".aew-input-row { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #e5e7eb; background: #fff; }",
    ".aew-input { flex: 1; border: 1px solid #d1d5db; border-radius: 22px; padding: 8px 14px; font-size: 14px; outline: none; }",
    ".aew-input:focus { border-color: currentColor; }",
    ".aew-send { border: none; border-radius: 50%; width: 38px; height: 38px; color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }",
    ".aew-send svg { width: 18px; height: 18px; fill: #fff; }",
    ".aew-send:disabled { opacity: .5; cursor: not-allowed; }",
    ".aew-banner { padding: 8px 12px; font-size: 12px; background: #fffbeb; color: #92400e; border-top: 1px solid #fde68a; }",
    ".aew-footnote { font-size: 10px; color: #9ca3af; text-align: center; padding: 4px; background: #fff; }",
  ].join("\n");

  var ICON_CHAT =
    '<svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/></svg>';
  var ICON_SEND =
    '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  var ICON_CLOSE = '<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
  var ICON_LOGO =
    '<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 15h-2v-2h2zm0-4h-2V7h2z"/></svg>';

  function Widget(cfg) {
    this.cfg = cfg;
    this.token = "";
    this.tokenExpiresAt = 0;
    this.widgetId = "";
    this.configuration = { chat: false, recommendations: false };
    this.mode = "chat";
    this.opened = false;
    this.typing = false;
    this.messagesEl = null;
    this.inputEl = null;
    this.productsInitialized = false;
    this.bannerEl = null;
    this.eventCount = 0;
  }

  Widget.prototype.emit = function (detail) {
    detail = detail || {};
    detail.version = VERSION;
    detail.widgetId = this.widgetId;
    detail.mode = this.mode;
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: detail }));
  };

  Widget.prototype.storageConversationId = function () {
    if (window.sessionStorage) {
      var stored = window.sessionStorage.getItem(CONVERSATION_STORAGE_KEY);
      if (!stored) {
        stored =
          "conv_" +
          (window.crypto && window.crypto.randomUUID
            ? window.crypto.randomUUID()
            : Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
        window.sessionStorage.setItem(CONVERSATION_STORAGE_KEY, stored);
      }
      return stored;
    }
    return "";
  };

  Widget.prototype.apiUrl = function (path) {
    return this.cfg.apiBase.replace(/\/+$/, "") + path;
  };

  Widget.prototype.hasToken = function () {
    return !!this.token && this.tokenExpiresAt - Date.now() / 1000 > TOKEN_REFRESH_LEAD_SECONDS;
  };

  Widget.prototype.bootstrap = function () {
    var self = this;
    return fetch(this.apiUrl("/api/v1/widget/bootstrap"), {
      method: "POST",
      headers: { "X-Widget-Key": this.cfg.widgetKey, Accept: "application/json" },
    }).then(function (res) {
      if (!res.ok) {
        return res.json().then(function (body) {
          throw new Error("bootstrap_" + res.status + ":" + (body && body.detail ? body.detail : res.statusText));
        });
      }
      return res.json();
    }).then(function (data) {
      self.token = data.access_token;
      self.tokenExpiresAt = Date.now() / 1000 + data.expires_in;
      self.widgetId = data.widget_id;
      self.configuration = data.configuration || self.configuration;
      self.emit({ status: "ready", configuration: self.configuration });
      return data;
    });
  };

  Widget.prototype.ensureToken = function () {
    if (this.hasToken()) return Promise.resolve();
    return this.bootstrap();
  };

  Widget.prototype.post = function (path, body) {
    var self = this;
    var attempt = function () {
      return fetch(self.apiUrl(path), {
        method: "POST",
        headers: {
          Authorization: "Bearer " + self.token,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(body),
      }).then(function (res) {
        if (res.status === 401) {
          return self.bootstrap().then(function () {
            return attempt();
          });
        }
        return res.json().then(function (data) {
          if (!res.ok) throw Object.assign(new Error(data.detail || res.statusText), { status: res.status, data: data });
          return data;
        });
      });
    };
    return this.ensureToken().then(attempt);
  };

  Widget.prototype.sendChat = function (message) {
    var body = { message: message, conversation_id: this.storageConversationId() };
    if (this.cfg.customerId) body.customer_id = this.cfg.customerId;
    return this.post("/api/v1/widget/chat", body);
  };

  Widget.prototype.sendRecommendations = function (message) {
    var body = { message: message };
    if (this.cfg.customerId) body.customer_id = this.cfg.customerId;
    return this.post("/api/v1/widget/recommendations", body);
  };

  /* ------------------------------- UI ------------------------------- */

  Widget.prototype.buildDom = function () {
    var self = this;
    var host = document.createElement("div");
    host.id = "ai-commerce-widget";
    host.attachShadow({ mode: "open" });

    var style = document.createElement("style");
    style.textContent = STYLES;
    host.shadowRoot.appendChild(style);

    var root = document.createElement("div");
    root.className = "aew-root aew-bottom-right";
    root.style.color = this.cfg.accentColor;
    host.shadowRoot.appendChild(root);

    this.fab = document.createElement("button");
    this.fab.className = "aew-fab";
    this.fab.style.background = this.cfg.accentColor;
    this.fab.setAttribute("aria-label", this.cfg.launcherText);
    this.fab.innerHTML = ICON_CHAT;
    this.fab.title = this.cfg.launcherText;
    this.fab.addEventListener("click", function () {
      self.open();
    });
    root.appendChild(this.fab);

    this.panel = document.createElement("div");
    this.panel.className = "aew-panel aew-bottom-right";
    this.panel.style.display = "none";

    var header = document.createElement("div");
    header.className = "aew-header";
    header.style.background = this.cfg.accentColor;
    header.innerHTML =
      '<div class="aew-header-title">' + ICON_LOGO + "<span>" + escapeHtml(this.cfg.launcherText) + "</span></div>";
    this.closeBtn = document.createElement("button");
    this.closeBtn.className = "aew-close";
    this.closeBtn.setAttribute("aria-label", "Close chat");
    this.closeBtn.innerHTML = ICON_CLOSE;
    this.closeBtn.addEventListener("click", function () {
      self.close();
    });
    header.appendChild(this.closeBtn);
    this.panel.appendChild(header);

    if (this.configuration.recommendations) {
      var tabs = document.createElement("div");
      tabs.className = "aew-tabs";
      this.chatTab = document.createElement("button");
      this.chatTab.className = "aew-tab aew-active";
      this.chatTab.textContent = "Chat";
      this.chatTab.addEventListener("click", function () {
        self.setMode("chat");
      });
      var recTab = document.createElement("button");
      recTab.className = "aew-tab";
      recTab.textContent = "Find products";
      recTab.addEventListener("click", function () {
        self.setMode("recommendations");
      });
      tabs.appendChild(this.chatTab);
      tabs.appendChild(recTab);
      this.panel.appendChild(tabs);
    }

    this.messagesEl = document.createElement("div");
    this.messagesEl.className = "aew-messages";
    this.panel.appendChild(this.messagesEl);

    this.bannerEl = document.createElement("div");
    this.bannerEl.className = "aew-banner";
    this.bannerEl.style.display = "none";
    this.panel.appendChild(this.bannerEl);

    var inputRow = document.createElement("div");
    inputRow.className = "aew-input-row";
    this.inputEl = document.createElement("input");
    this.inputEl.className = "aew-input";
    this.inputEl.type = "text";
    this.inputEl.placeholder = this.mode === "recommendations" ? "e.g. wireless keyboard under $80" : "Type a message...";
    this.inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !self.typing) self.submitInput();
    });
    var send = document.createElement("button");
    send.className = "aew-send";
    send.style.background = this.cfg.accentColor;
    send.setAttribute("aria-label", "Send");
    send.innerHTML = ICON_SEND;
    send.addEventListener("click", function () {
      self.submitInput();
    });
    inputRow.appendChild(this.inputEl);
    inputRow.appendChild(send);
    this.panel.appendChild(inputRow);

    var footnote = document.createElement("div");
    footnote.className = "aew-footnote";
    footnote.textContent = "Powered by AI";
    this.panel.appendChild(footnote);

    host.shadowRoot.appendChild(this.panel);

    document.body.appendChild(host);
    this.host = host;
    this.sendBtn = send;
  };

  Widget.prototype.setMode = function (mode) {
    this.mode = mode;
    if (this.chatTab) {
      this.chatTab.className = "aew-tab" + (mode === "chat" ? " aew-active" : "");
      var recTab = this.chatTab.nextElementSibling;
      if (recTab) recTab.className = "aew-tab" + (mode === "recommendations" ? " aew-active" : "");
    }
    this.inputEl.placeholder =
      mode === "recommendations" ? "e.g. wireless keyboard under $80" : "Type a message...";
    if (mode === "recommendations" && !this.productsInitialized) {
      var tips = this.messagesEl.querySelector(".aew-msg-bot");
      if (!tips) {
        this.appendBot(
          "Hi, I can find products for you. Tell me what you need (budget, brand, specs) and I will fetch matching products from the store catalog."
        );
        this.productsInitialized = true;
      }
    }
    this.emit({ status: "mode", mode: mode });
  };

  Widget.prototype.open = function () {
    var self = this;
    this.opened = true;
    this.panel.style.display = "flex";
    this.fab.style.display = "none";
    this.inputEl.focus();
    if (this.configuration.recommendations) this.setMode(this.mode);

    this.ensureToken()
      .then(function () {
        var messages = self.messagesEl.querySelectorAll(".aew-msg");
        if (!messages.length) {
          var enabled = [];
          if (self.configuration.chat) enabled.push("chat");
          if (self.configuration.recommendations) enabled.push("product recommendations");
          self.appendBot(
            "Welcome! I can help with " +
              (enabled.length ? enabled.join(" and ") : "chat") +
              ". What would you like to know?"
          );
        }
      })
      .catch(function (err) {
        self.appendError("Could not initialize the assistant: " + self.friendlyError(err));
      });
  };

  Widget.prototype.close = function () {
    this.opened = false;
    this.panel.style.display = "none";
    this.fab.style.display = "flex";
    this.emit({ status: "closed" });
  };

  Widget.prototype.setTyping = function (on) {
    this.typing = on;
    this.sendBtn.disabled = on;
    if (on) {
      var t = document.createElement("div");
      t.className = "aew-typing";
      t.innerHTML = "<i></i><i></i><i></i>";
      this.messagesEl.appendChild(t);
      this.typingEl = t;
    } else if (this.typingEl && this.typingEl.parentNode) {
      this.typingEl.parentNode.removeChild(this.typingEl);
      this.typingEl = null;
    }
    this.scrollBottom();
  };

  Widget.prototype.scrollBottom = function () {
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  };

  Widget.prototype.appendUser = function (text) {
    var el = document.createElement("div");
    el.className = "aew-msg aew-msg-user";
    el.style.background = this.cfg.accentColor;
    el.textContent = text;
    this.messagesEl.appendChild(el);
    this.scrollBottom();
    return el;
  };

  Widget.prototype.appendBot = function (html) {
    var el = document.createElement("div");
    el.className = "aew-msg aew-msg-bot";
    el.innerHTML = html;
    this.messagesEl.appendChild(el);
    this.scrollBottom();
    return el;
  };

  Widget.prototype.appendError = function (text) {
    var el = document.createElement("div");
    el.className = "aew-msg aew-msg-error";
    el.textContent = text;
    this.messagesEl.appendChild(el);
    this.scrollBottom();
    return el;
  };

  Widget.prototype.appendSources = function (citations) {
    var box = document.createElement("div");
    box.className = "aew-sources";
    var toggle = document.createElement("button");
    toggle.className = "aew-sources-toggle";
    toggle.textContent = "View sources (" + citations.length + ")";
    toggle.addEventListener("click", function () {
      if (!box.querySelector(".aew-sources-list")) {
        var list = document.createElement("ul");
        list.className = "aew-sources-list";
        citations.forEach(function (c) {
          var li = document.createElement("li");
          var title = document.createElement("strong");
          title.textContent = c.document_title || "Source " + c.index;
          li.appendChild(title);
          if (c.content_snippet) {
            li.appendChild(document.createTextNode(" - " + c.content_snippet.slice(0, 140)));
          }
          list.appendChild(li);
        });
        box.appendChild(list);
      } else {
        var existing = box.querySelector(".aew-sources-list");
        existing.parentNode.removeChild(existing);
      }
    });
    box.appendChild(toggle);
    this.messagesEl.appendChild(box);
    this.scrollBottom();
  };

  Widget.prototype.appendProducts = function (data) {
    var grid = document.createElement("div");
    grid.className = "aew-products";
    (data.products || []).forEach(function (p) {
      var card = document.createElement("div");
      card.className = "aew-product";
      var img = document.createElement("img");
      img.src = p.image_url || "";
      img.alt = p.title || "";
      card.appendChild(img);
      var title = document.createElement("div");
      title.className = "aew-product-title";
      title.textContent = p.title || "";
      card.appendChild(title);
      var price = document.createElement("div");
      price.className = "aew-product-price";
      price.textContent = (p.price || "") + (p.currency ? " " + p.currency : "");
      card.appendChild(price);
      if (p.match_reasons && p.match_reasons.length) {
        var reasons = document.createElement("div");
        reasons.className = "aew-reasons";
        reasons.textContent = "Matches: " + p.match_reasons.join(", ");
        card.appendChild(reasons);
      }
      if (p.product_url) {
        var link = document.createElement("a");
        link.className = "aew-product-link";
        link.href = p.product_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.style.background = this.cfg.accentColor;
        link.textContent = "View product";
        card.appendChild(link);
      }
      grid.appendChild(card);
    });
    this.messagesEl.appendChild(grid);
    this.scrollBottom();
  };

  Widget.prototype.showBanner = function (text) {
    this.bannerEl.textContent = text;
    this.bannerEl.style.display = "block";
  };

  Widget.prototype.hideBanner = function () {
    this.bannerEl.style.display = "none";
  };

  Widget.prototype.friendlyError = function (err) {
    if (err && err.status === 429) return "Too many requests. Please wait a moment and try again.";
    if (err && err.status === 401) return "Session expired. Please try again.";
    if (err && err.status === 403) return "This feature is not enabled for this widget.";
    if (err && err.data && err.data.detail) return err.data.detail;
    return (
      (err && err.message ? err.message : String(err)).replace(/^bootstrap_\d+:[^:]*:/, "") +
      ". Check that the widget key and API base are correct."
    );
  };

  Widget.prototype.submitInput = function () {
    var text = this.inputEl.value.trim();
    if (!text || this.typing) return;
    this.inputEl.value = "";

    var isRec = this.mode === "recommendations" && this.configuration.recommendations;
    this.appendUser(text);
    this.setTyping(true);
    this.hideBanner();
    this.emit({ status: isRec ? "recommendation_started" : "chat_started", query: text });

    var promise = isRec ? this.sendRecommendations(text) : this.sendChat(text);
    var self = this;
    promise
      .then(function (data) {
        if (isRec) {
          if (!data.products || !data.products.length) {
            self.appendBot("I could not find matching products in the store catalog.");
          } else {
            self.appendBot(escapeHtml(data.rationale || "Here are some products that match:"));
            self.appendProducts(data);
          }
        } else {
          self.appendBot(formatText(data.response));
          if (data.citations && data.citations.length) self.appendSources(data.citations);
          if (data.confidence_score < 0.3) {
            var box = self.messagesEl.querySelectorAll(".aew-sources");
            var last = box[box.length - 1];
            if (last) {
              last.insertAdjacentHTML(
                "afterend",
                '<div class="aew-msg aew-msg-bot">I could not find a confident answer. Consider contacting the store for human support.</div>'
              );
            }
          }
        }
        self.emit({
          status: isRec ? "recommendation_done" : "chat_done",
          count: isRec && data.products ? data.products.length : undefined,
        });
      })
      .catch(function (err) {
        if (err && err.status === 429) {
          var retry = err.data && err.data.reset_seconds;
          self.showBanner("Rate limit reached. Try again in " + (retry || 60) + "s.");
        }
        self.appendError(self.friendlyError(err));
        self.emit({ status: "error", error: err && err.status ? err.status : "network" });
      })
      .then(function () {
        self.setTyping(false);
      });
  };

  Widget.prototype.destroy = function () {
    if (this.host && this.host.parentNode) this.host.parentNode.removeChild(this.host);
    this.host = null;
  };

  function init() {
    var cfg = readConfig();
    if (!cfg.widgetKey) {
      window.dispatchEvent(
        new CustomEvent(EVENT_NAME, { detail: { status: "error", error: "missing_key" } })
      );
      return null;
    }
    var widget = new Widget(cfg);
    widget.buildDom();
    widget.bootstrap().catch(function (err) {
      widget.appendError("Widget initialization failed: " + widget.friendlyError(err));
      widget.emit({ status: "error", error: "bootstrap" });
    });
    return widget;
  }

  if (window.AiCommerceWidget) {
    if (window.AiCommerceWidget.current) window.AiCommerceWidget.current.destroy();
  }

  window.AiCommerceWidget = {
    version: VERSION,
    init: function (options) {
      // Programmatic init: options.key, options.apiBase, options.customerId, options.launcherText, options.accentColor
      if (options) {
        var existing = lastScript();
        if (existing) {
          if (options.key) existing.setAttribute("data-widget-key", options.key);
          if (options.apiBase) existing.setAttribute("data-api-base", options.apiBase);
          if (options.customerId) existing.setAttribute("data-customer-id", options.customerId);
          if (options.launcherText) existing.setAttribute("data-launcher-text", options.launcherText);
          if (options.accentColor) existing.setAttribute("data-accent-color", options.accentColor);
        }
      }
      window.AiCommerceWidget.current = init();
      return window.AiCommerceWidget.current;
    },
    destroy: function () {
      if (window.AiCommerceWidget.current) {
        window.AiCommerceWidget.current.destroy();
        window.AiCommerceWidget.current = null;
      }
    },
  };

  window.AiCommerceWidget.current = init();
})();