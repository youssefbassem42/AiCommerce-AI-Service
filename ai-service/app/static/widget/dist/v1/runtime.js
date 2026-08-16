(()=>{var xe=`
:host {
  all: initial;
  --ac-widget-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --ac-widget-primary: #2563eb;
  --ac-widget-primary-hover: #1d4ed8;
  --ac-widget-bg: #ffffff;
  --ac-widget-text: #1f2937;
  --ac-widget-text-secondary: #6b7280;
  --ac-widget-border: #e5e7eb;
  --ac-widget-user-bubble: #2563eb;
  --ac-widget-user-text: #ffffff;
  --ac-widget-assistant-bubble: #f3f4f6;
  --ac-widget-radius: 16px;
  --ac-widget-shadow: 0 8px 30px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.12);
  --ac-widget-z: 2147483000;
  --ac-widget-error: #b91c1c;
}

:host([data-position="left"]) {
  --ac-widget-side: left;
}
:host([data-position="right"]) {
  --ac-widget-side: right;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

.widget-root {
  position: fixed;
  z-index: var(--ac-widget-z);
  inset-block-end: 16px;
  inset-inline-end: 16px;
  inset-inline-start: auto;
  font-family: var(--ac-widget-font);
  color: var(--ac-widget-text);
  line-height: 1.45;
  font-size: 14px;
}

:host([data-position="left"]) .widget-root {
  inset-inline-end: auto;
  inset-inline-start: 16px;
}

.widget-root * {
  font-family: var(--ac-widget-font);
}

/* ---------- Launcher ---------- */

.launcher {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 60px;
  height: 60px;
  border: none;
  border-radius: 50%;
  background: var(--ac-widget-primary);
  color: #ffffff;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
  transition: transform 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease;
  position: relative;
}

.launcher:hover {
  background: var(--ac-widget-primary-hover);
  transform: translateY(-2px);
}
.launcher:active {
  transform: translateY(0) scale(0.97);
}
.launcher:focus-visible {
  outline: 2px solid var(--ac-widget-primary);
  outline-offset: 3px;
}

.launcher svg {
  width: 26px;
  height: 26px;
  fill: currentColor;
}

.launcher .launcher-close-svg {
  display: none;
}
.launcher[aria-expanded="true"] .launcher-open-svg {
  display: none;
}
.launcher[aria-expanded="true"] .launcher-close-svg {
  display: block;
}

/* ---------- Panel ---------- */

.panel {
  position: absolute;
  inset-block-end: 72px;
  inset-inline-end: 0;
  width: min(400px, calc(100vw - 32px));
  height: min(640px, calc(100vh - 120px));
  max-height: calc(100dvh - 120px);
  background: var(--ac-widget-bg);
  border: 1px solid var(--ac-widget-border);
  border-radius: var(--ac-widget-radius);
  box-shadow: var(--ac-widget-shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  opacity: 0;
  transform: translateY(12px) scale(0.98);
  transform-origin: bottom right;
  pointer-events: none;
  transition: opacity 0.18s ease, transform 0.18s ease;
  visibility: hidden;
}

:host([data-position="left"]) .panel {
  transform-origin: bottom left;
}

.panel.is-open {
  opacity: 1;
  transform: translateY(0) scale(1);
  pointer-events: auto;
  visibility: visible;
}

@media (max-width: 480px) {
  .widget-root {
    inset-block-end: 0;
    inset-inline-end: 0;
  }
  :host([data-position="left"]) .widget-root {
    inset-inline-start: 0;
  }
  .panel {
    inset-block-end: 76px;
    inset-inline-end: 8px;
    inset-inline-start: 8px;
    width: auto;
    height: calc(100dvh - 92px);
    max-height: calc(100dvh - 92px);
  }
  .launcher {
    width: 56px;
    height: 56px;
  }
}

/* ---------- Header ---------- */

.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: var(--ac-widget-primary);
  color: #ffffff;
  flex-shrink: 0;
}

.panel-header-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.panel-header-avatar svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.panel-header-title {
  font-weight: 600;
  font-size: 15px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel-header-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.icon-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #ffffff;
  cursor: pointer;
  padding: 0;
}
.icon-button:hover {
  background: rgba(255, 255, 255, 0.16);
}
.icon-button:focus-visible {
  outline: 2px solid #ffffff;
  outline-offset: 1px;
}
.icon-button svg {
  width: 16px;
  height: 16px;
  fill: currentColor;
}

/* ---------- Message area ---------- */

.message-area {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  scrollbar-width: thin;
}

.welcome-message {
  margin: auto 0 0;
  text-align: center;
  color: var(--ac-widget-text-secondary);
  background: var(--ac-widget-assistant-bubble);
  border-radius: 12px;
  padding: 12px 16px;
  max-width: 85%;
  align-self: center;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ---------- Bubbles ---------- */

.bubble-row {
  display: flex;
  width: 100%;
}
.bubble-row.user {
  justify-content: flex-end;
}
.bubble-row.assistant {
  justify-content: flex-start;
}

.bubble-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 84%;
  min-width: 0;
}

.bubble {
  max-width: 100%;
  border-radius: 14px;
  padding: 10px 14px;
  font-size: 14px;
  word-break: break-word;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.bubble.user {
  background: var(--ac-widget-user-bubble);
  color: var(--ac-widget-user-text);
  border-bottom-right-radius: 4px;
}

.bubble.assistant {
  background: var(--ac-widget-assistant-bubble);
  color: var(--ac-widget-text);
  border-bottom-left-radius: 4px;
}

.bubble-error {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}

.bubble-meta {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: var(--ac-widget-text-secondary);
  opacity: 0.85;
}

/* ---------- Citations ---------- */

.citations {
  margin-top: 8px;
  border-top: 1px solid var(--ac-widget-border);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 100%;
}

.citations-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ac-widget-text-secondary);
}

.citation {
  font-size: 12px;
  color: var(--ac-widget-text-secondary);
  background: #ffffff;
  border: 1px solid var(--ac-widget-border);
  border-radius: 8px;
  padding: 6px 10px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.citation-index {
  font-weight: 600;
  color: var(--ac-widget-primary);
  flex-shrink: 0;
  min-width: 16px;
}

.citation-title {
  font-weight: 600;
  color: var(--ac-widget-text);
  word-break: break-word;
}

.citation-snippet {
  word-break: break-word;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* ---------- Recommendation cards ---------- */

.recommendations {
  margin-top: 10px;
  max-width: 100%;
}

.recommendations-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ac-widget-text-secondary);
  margin-bottom: 8px;
}

.recommendations-scroller {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scrollbar-width: none;
  padding-bottom: 4px;
}
.recommendations-scroller::-webkit-scrollbar {
  display: none;
}
.recommendations-scroller:focus-visible {
  outline: 2px solid var(--ac-widget-primary);
  outline-offset: 2px;
  border-radius: 6px;
}

.recommendation-card {
  flex: 0 0 220px;
  scroll-snap-align: start;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #ffffff;
  border: 1px solid var(--ac-widget-border);
  border-radius: 10px;
  padding: 10px;
  text-decoration: none;
  color: var(--ac-widget-text);
  transition: box-shadow 0.12s ease, border-color 0.12s ease;
}

.recommendation-card:hover {
  border-color: var(--ac-widget-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.recommendation-card:focus-visible {
  outline: 2px solid var(--ac-widget-primary);
  outline-offset: 2px;
}

.recommendation-image {
  width: 100%;
  height: 110px;
  border-radius: 8px;
  object-fit: cover;
  background: var(--ac-widget-assistant-bubble);
  flex-shrink: 0;
}

.recommendation-body {
  min-width: 0;
}

.recommendation-title {
  font-weight: 600;
  font-size: 13px;
  word-break: break-word;
}

.recommendation-price {
  font-size: 13px;
  color: var(--ac-widget-primary);
  font-weight: 600;
  margin-top: 2px;
}

.recommendation-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.reason-badge {
  font-size: 11px;
  background: #eff6ff;
  color: var(--ac-widget-primary);
  border-radius: 999px;
  padding: 1px 8px;
}

.recommendations-controls {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 8px;
}

.carousel-arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 999px;
  border: 1px solid var(--ac-widget-border);
  background: transparent;
  color: var(--ac-widget-text-secondary);
  cursor: pointer;
  transition: border-color 0.12s ease, color 0.12s ease;
}
.carousel-arrow:hover {
  border-color: var(--ac-widget-primary);
  color: var(--ac-widget-primary);
}
.carousel-arrow:focus-visible {
  outline: 2px solid var(--ac-widget-primary);
  outline-offset: 2px;
}
.carousel-arrow-icon {
  width: 16px;
  height: 16px;
}

.recommendation-empty {
  font-size: 12px;
  color: var(--ac-widget-text-secondary);
  background: var(--ac-widget-assistant-bubble);
  border-radius: 8px;
  padding: 8px 12px;
}

.recommendations-rationale {
  font-size: 12px;
  color: var(--ac-widget-text);
  background: var(--ac-widget-assistant-bubble);
  border-radius: 8px;
  padding: 6px 10px;
  margin-bottom: 8px;
}

.recommendation-rating {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--ac-widget-text-secondary);
}

.rating-icon {
  width: 14px;
  height: 14px;
  fill: #f59e0b;
  flex-shrink: 0;
}

.rating-value {
  font-weight: 600;
}

.recommendation-price-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.price-original {
  font-size: 12px;
  color: var(--ac-widget-text-secondary);
  text-decoration: line-through;
}

.price-final {
  font-size: 14px;
  color: var(--ac-widget-primary);
  font-weight: 700;
}

.discount-badge {
  font-size: 11px;
  font-weight: 700;
  color: #166534;
  background: #dcfce7;
  border-radius: 999px;
  padding: 1px 7px;
}

.availability-badge {
  align-self: flex-start;
  font-size: 11px;
  border-radius: 999px;
  padding: 1px 8px;
  margin-top: 6px;
  font-weight: 600;
}

.availability-badge.in-stock {
  color: #166534;
  background: #dcfce7;
}

.availability-badge.out-of-stock {
  color: #991b1b;
  background: #fee2e2;
}

.recommendation-cta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ac-widget-primary);
}

.cta-icon {
  width: 14px;
  height: 14px;
  fill: currentColor;
}

/* ---------- Bundle cards ---------- */

.bundle-card {
  margin-top: 10px;
  max-width: 100%;
  background: #ffffff;
  border: 1px solid var(--ac-widget-border);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bundle-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bundle-item,
.bundle-item-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  border-radius: 6px;
  padding: 2px 0;
}

.bundle-item-link {
  text-decoration: none;
  color: var(--ac-widget-text);
  transition: color 0.12s ease;
}

.bundle-item-link:hover {
  color: var(--ac-widget-primary);
}

.bundle-item-name {
  font-weight: 600;
  word-break: break-word;
}

.bundle-item-price {
  font-size: 12px;
  color: var(--ac-widget-text-secondary);
  white-space: nowrap;
}

.bundle-totals {
  border-top: 1px solid var(--ac-widget-border);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bundle-total-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.bundle-total-label {
  color: var(--ac-widget-text-secondary);
}

.bundle-total-original {
  font-weight: 600;
}

.bundle-total-discount {
  color: #166534;
  font-weight: 700;
}

.bundle-total-final {
  font-size: 14px;
  font-weight: 700;
  color: var(--ac-widget-primary);
}

.bundle-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 2px;
}

.bundle-copy-button,
.bundle-shop-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-decoration: none;
}

.bundle-action-icon {
  width: 14px;
  height: 14px;
  fill: currentColor;
}

.bundle-copy-button .bundle-action-icon {
  fill: currentColor;
}

/* ---------- Escalation ---------- */

.bubble-escalation {
  border-color: var(--ac-widget-error);
}

.escalation-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: #991b1b;
  background: #fee2e2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 8px 12px;
}

.escalation-icon {
  width: 16px;
  height: 16px;
  fill: currentColor;
  flex-shrink: 0;
}

/* ---------- Action / suggestion buttons ---------- */

.action-button {
  align-self: flex-start;
  margin-top: 8px;
  border: 1px solid var(--ac-widget-primary);
  color: var(--ac-widget-primary);
  background: transparent;
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: background-color 0.12s ease, color 0.12s ease;
}

.action-button:hover {
  background: var(--ac-widget-primary);
  color: #ffffff;
}
.action-button:focus-visible {
  outline: 2px solid var(--ac-widget-primary);
  outline-offset: 2px;
}

.retry-row {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}

/* ---------- Typing indicator ---------- */

.typing {
  display: inline-flex;
  gap: 4px;
  padding: 4px 2px;
}
.typing-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ac-widget-text-secondary);
  animation: ac-widget-typing 1.2s infinite ease-in-out;
}
.typing-dot:nth-child(2) {
  animation-delay: 0.15s;
}
.typing-dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes ac-widget-typing {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

/* ---------- Status / error states ---------- */

.state-box {
  margin: auto;
  text-align: center;
  color: var(--ac-widget-text-secondary);
  padding: 20px 16px;
}

.state-box-title {
  font-weight: 600;
  color: var(--ac-widget-text);
  margin-bottom: 6px;
}

.state-box-text {
  font-size: 13px;
  line-height: 1.5;
}

/* ---------- Input ---------- */

.input-bar {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--ac-widget-border);
  background: var(--ac-widget-bg);
  flex-shrink: 0;
}

.input-textarea {
  flex: 1;
  resize: none;
  border: 1px solid var(--ac-widget-border);
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  color: var(--ac-widget-text);
  background: #ffffff;
  max-height: 120px;
  min-height: 40px;
  outline: none;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}

.input-textarea:focus {
  border-color: var(--ac-widget-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.input-textarea::placeholder {
  color: var(--ac-widget-text-secondary);
}

.send-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 12px;
  background: var(--ac-widget-primary);
  color: #ffffff;
  cursor: pointer;
  flex-shrink: 0;
  transition: background-color 0.12s ease, opacity 0.12s ease;
}

.send-button:hover:not(:disabled) {
  background: var(--ac-widget-primary-hover);
}
.send-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.send-button:focus-visible {
  outline: 2px solid var(--ac-widget-primary);
  outline-offset: 2px;
}

.send-button svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.input-hint {
  position: absolute;
  inset-block-end: 74px;
  inset-inline-end: 8px;
  inset-inline-start: 8px;
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 12px;
  text-align: center;
  box-shadow: var(--ac-widget-shadow);
}

:host([data-position="left"]) .input-hint {
  inset-inline-end: 8px;
  inset-inline-start: 8px;
}

:host([hidden]) {
  display: none;
}

@media (prefers-reduced-motion: reduce) {
  .panel,
  .launcher,
  .typing-dot {
    transition: none;
    animation: none;
  }
}
`;var h=Object.freeze({INITIALIZING:"INITIALIZING",READY:"READY",OPENING:"OPENING",SENDING:"SENDING",RECEIVING:"RECEIVING",ERROR:"ERROR",AUTHENTICATION_FAILED:"AUTHENTICATION_FAILED",RATE_LIMITED:"RATE_LIMITED",DISABLED:"DISABLED"}),W=class{constructor(e=h.INITIALIZING){this._state=e,this._listeners=new Set}get state(){return this._state}is(...e){return e.includes(this._state)}set(e,t=null){let n=this._state;if(n!==e){this._state=e;for(let s of[...this._listeners])try{s(e,n,t)}catch{}}}subscribe(e){return this._listeners.add(e),()=>this._listeners.delete(e)}};var w=Object.freeze({HTTP:"http",NETWORK:"network",TIMEOUT:"timeout",ABORTED:"aborted",INVALID_RESPONSE:"invalid_response"}),Ue=new Set([500,502,503,504]);var x=class extends Error{constructor({status:e=null,kind:t=w.HTTP,message:n="Request failed",detail:s=null,retryAfterSeconds:r=null,headers:a={},retryable:c=!1,requestId:d=null}){super(n),this.name="ApiError",this.status=e,this.kind=t,this.detail=s,this.retryAfterSeconds=r,this.headers=a,this.retryable=c,this.requestId=d}isRateLimited(){return this.status===429}isAuth(){return this.status===401}isForbidden(){return this.status===403}is5xx(){return this.status!==null&&Ue.has(this.status)}isNetwork(){return this.kind===w.NETWORK||this.kind===w.TIMEOUT}rateLimitHeaders(){var e,t,n,s;return{retryAfter:ze(this.headers["retry-after"]),limit:(e=this.headers["x-ratelimit-limit"])!=null?e:null,remaining:(t=this.headers["x-ratelimit-remaining"])!=null?t:null,reset:(n=this.headers["x-ratelimit-reset"])!=null?n:null,tier:(s=this.headers["x-ratelimit-tier"])!=null?s:null}}};function ze(i){if(i==null||i==="")return null;let e=Number(i);if(Number.isFinite(e)&&e>=0)return e;let t=Date.parse(i);return Number.isFinite(t)?Math.max(0,Math.round((t-Date.now())/1e3)):null}function we(i,e){return i.isAuth()||i.isRateLimited()||i.status===422||i.status===400||i.status===404||i.status===403?!1:i.is5xx()||i.isNetwork()?e<1:!1}function ye(i){let t=Math.random()*.3+.85;return Math.min(5e3,Math.round(500*Math.pow(2,i)*t))}var Fe=3e4,He=1;function je(){if(typeof crypto!="undefined"&&crypto.randomUUID)return crypto.randomUUID();let i=new Uint8Array(16);return(crypto||globalThis.crypto).getRandomValues(i),Array.from(i,e=>e.toString(16).padStart(2,"0")).join("")}var _e=i=>new Promise(e=>setTimeout(e,i)),P=class{constructor({baseUrl:e,getToken:t,bootstrap:n,timeoutMs:s=Fe,backoff:r=ye}){this.baseUrl=String(e).replace(/\/+$/,""),this.getToken=t,this.bootstrap=n,this.timeoutMs=s,this.backoff=r,this._fetch=typeof fetch!="undefined"?fetch.bind(globalThis):null}async request(e){if(!this._fetch)throw new x({kind:w.NETWORK,message:"Fetch API is not available in this environment."});let{path:t,query:n,body:s,headers:r={},auth:a=!1,isBootstrap:c=!1,widgetKey:d=null,timeoutMs:l=this.timeoutMs}=e,u=this.buildUrl(t,n),p=new Headers(r);if(p.set("Accept","application/json"),p.set("X-Correlation-ID",je()),s!=null&&p.set("Content-Type","application/json"),c){if(!d)throw new x({kind:w.INVALID_RESPONSE,message:"Widget key missing for bootstrap."});p.set("X-Widget-Key",d)}else if(a){let f=this.getToken();f&&p.set("Authorization",`Bearer ${f}`)}let b=p.get("X-Correlation-ID");for(let f=0;;f+=1){let S;try{S=await this._fetchWithTimeout(u,p,s,l)}catch(O){if(qe(O))throw new x({kind:w.TIMEOUT,message:"Request timed out.",requestId:b});if(We(f)){await _e(this.backoff(f));continue}throw new x({kind:w.NETWORK,message:"Unable to connect to the assistant.",retryable:!0,requestId:b})}let{data:B,status:I}=await Ge(S);if(I>=200&&I<300)return this.resetAuthRetry(),{data:B,status:I,headers:S.headers};let R=$e(S,B,I,b);if(R.isAuth()&&a&&this.bootstrap&&!this._authRetried){this._authRetried=!0;try{await this.bootstrap({replacedToken:!0});continue}catch{throw new x({kind:w.HTTP,status:401,message:"Your AI assistant session expired. Reconnecting...",retryable:!1,requestId:b})}}if(we(R,f)){await _e(this.backoff(f));continue}throw R}}resetAuthRetry(){this._authRetried=!1}buildUrl(e,t){let n=new URL(`${this.baseUrl}${e.startsWith("/")?e:`/${e}`}`);if(t)for(let[s,r]of Object.entries(t))r!=null&&r!==""&&n.searchParams.set(s,String(r));return n}post(e,t,n={}){let{query:s,...r}=n;return this.request({path:e,query:s,body:t,...r})}get(e,t,n={}){return this.request({path:e,query:t,...n})}async _fetchWithTimeout(e,t,n,s){return this._fetchJson("POST",e,t,n,s)}async _fetchJson(e,t,n,s,r){let a=new AbortController,c=setTimeout(()=>a.abort(),r);try{return await this._fetch(t,{method:e,headers:n,body:s!=null?JSON.stringify(s):void 0,signal:a.signal,credentials:"omit",cache:"no-store"})}finally{clearTimeout(c)}}};async function Ge(i){let e=await i.text(),t=i.headers.get("content-type")||"",n=null;if(e&&t.includes("application/json"))try{n=JSON.parse(e)}catch{n=null}return{data:n,status:i.status}}function $e(i,e,t,n){let s={};for(let d of["retry-after","x-ratelimit-limit","x-ratelimit-remaining","x-ratelimit-reset","x-ratelimit-tier"]){let l=i.headers.get(d);l!==null&&(s[d]=l)}let r=s["retry-after"]!=null?Number(s["retry-after"]):null,a=null;e&&typeof e=="object"&&typeof e.detail=="string"&&(a=e.detail);let c=t>=500;return new x({status:t,kind:w.HTTP,message:`Request failed with status ${t}`,detail:a,retryAfterSeconds:Number.isFinite(r)?r:null,headers:s,retryable:c,requestId:n})}function We(i){return i<He}function qe(i){return i&&(i.name==="AbortError"||i.name==="TimeoutError")}var L=class extends Error{constructor(e){super(e),this.name="BootstrapParseError"}},q=class{static adapt(e){if(!e||typeof e!="object"||Array.isArray(e))throw new L("Bootstrap response is not an object.");let{access_token:t,expires_in:n,widget_id:s,configuration:r}=e;if(typeof t!="string"||t.length===0)throw new L("Bootstrap response missing access_token.");let a=Number(n);if(!Number.isFinite(a)||a<=0)throw new L("Bootstrap response missing valid expires_in.");if(typeof s!="string"||s.length===0)throw new L("Bootstrap response missing widget_id.");let c=r&&typeof r=="object"?r:{};return{accessToken:t,expiresIn:Math.floor(a),widgetId:s,configuration:{chat:c.chat===!0,recommendations:c.recommendations===!0}}}};var Ke=30,K=class{constructor({widgetKey:e,apiClient:t,marginSeconds:n=Ke,now:s=()=>Math.floor(Date.now()/1e3)}){this.widgetKey=e,this.apiClient=t,this.marginSeconds=n,this._now=s,this._token=null,this._expiresAt=0,this._inFlight=null,this._bootstrapError=null,this._bootstrapDone=!1}get hasToken(){return this._token!==null}getToken(){return this._token}isTokenExpired(){return this._token?this._now()>=this._expiresAt-this.marginSeconds:!0}get expiresInSeconds(){return Math.max(0,this._expiresAt-this._now())}seedFromSlot(){let n=null;try{n=typeof window!="undefined"?window.__AICommerce__:null}catch{return null}if(!n||!n.session)return null;let t=n.session;if(!t||typeof t.access_token!="string"||!t.access_token)return null;let a;try{a=q.adapt(t)}catch{return null}this._token=a.accessToken;let s=this._now();return this._expiresAt=s+a.expiresIn,this._bootstrapError=null,this._bootstrapDone=!0,delete window.__AICommerce__,a}async bootstrap(e={}){let{force:t=!1}=e;return this._inFlight?this._inFlight:(this._bootstrapDone=!1,this._inFlight=this._runBootstrap(t).finally(()=>{this._inFlight=null,this._bootstrapDone=!0}),this._inFlight)}async _runBootstrap(e){try{let{data:t}=await this.apiClient.post("/api/v1/widget/bootstrap",void 0,{isBootstrap:!0,auth:!1,widgetKey:this.widgetKey}),n=q.adapt(t);this._token=n.accessToken;let s=this._now();return this._expiresAt=s+n.expiresIn,this._bootstrapError=null,n}catch(t){throw this._token=null,this._expiresAt=0,this._bootstrapError=t instanceof x?t:new x({kind:w.NETWORK,message:"Bootstrap failed."}),this._bootstrapError}}async ensureToken(){if(!this.isTokenExpired())return this._token;if(await this.bootstrap(),!this._token)throw new x({kind:w.INVALID_RESPONSE,message:"Bootstrap did not return an access token."});return this._token}async refresh(){return this.bootstrap({force:!0})}clearBootstrapError(){this._bootstrapError=null}get lastBootstrapError(){return this._bootstrapError}reset(){this._token=null,this._expiresAt=0,this._inFlight=null,this._bootstrapError=null}};var Ve=/^(https?:|mailto:)/i;function pe(i){if(typeof i!="string"||i.length===0||i.length>2048)return!1;let e=i.trim();if(!Ve.test(e))return!1;try{let t=new URL(e);return["http:","https:","mailto:"].includes(t.protocol)}catch{return!1}}function V(i){return i==null?"":String(i).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/g,"")}function T(i,e){if(!pe(i))return null;let t=e.createElement("a");return t.href=i,t.target="_blank",t.rel="noopener noreferrer nofollow",t}function m(i){return typeof i=="string"&&i.length>0?i:null}function C(i,e=null){if(i==null||i==="")return e;let t=Number(i);return Number.isFinite(t)?t:e}function ve(i,e=null){return i==null?e:!!i}function U(i,e){if(!i||typeof i!="object"||Array.isArray(i))return null;let t=Array.isArray(i.specs)?i.specs.map(d=>d&&typeof d=="object"&&!Array.isArray(d)?{name:m(d.name),value:m(d.value)}:null).filter(d=>d!==null&&(d.name!==null||d.value!==null)).slice(0,12):[],n=Array.isArray(i.match_reasons)?i.match_reasons.filter(d=>typeof d=="string"&&d.length>0).slice(0,6):[],s=m(i.price),r=m(i.final_price)||m(i.price_after_discount),a=C(i.discount_pct,null),c=r!==null&&r!==s;return{id:m(i.product_id)||`product_${e}`,title:m(i.title)||null,price:s,originalPrice:m(i.original_price)||s,discountedPrice:c?r:null,discountPct:a,currency:m(i.currency),imageUrl:m(i.image_url),productUrl:m(i.product_url),rating:C(i.rating,null),inStock:ve(i.in_stock,null),stockQuantity:C(i.stock_quantity,null),specs:t,matchReasons:n}}function Ye(i,e){if(!i||typeof i!="object"||Array.isArray(i))return null;let t=m(i.price_after_discount),n=m(i.original_price);return{id:m(i.product_id)||`bundle_item_${e}`,title:m(i.title)||null,originalPrice:n,priceAfterDiscount:t!==null&&t!==n?t:null,discountPct:C(i.discount_pct,null),productUrl:m(i.product_url),imageUrl:m(i.image_url)}}function Ee(i){if(!i||typeof i!="object"||Array.isArray(i))return null;let e=(Array.isArray(i.items)?i.items:[]).map(Ye).filter(l=>l!==null).slice(0,12),t=m(i.total_original),n=m(i.total_discount),s=C(t,null),r=C(n,null),a=C(i.discount_pct,null);a===null&&s!==null&&r!==null&&s>0&&(a=Math.round(r/s*1e3)/10);let c=C(i.final_price,null),d=c!==null?String(c):s!==null&&r!==null?String(Math.round((s-r)*100)/100):null;return{items:e,totalOriginal:t,totalDiscount:n,discountPct:a,finalTotal:d,currency:m(i.currency),promoCode:m(i.promo_code),withinBudget:ve(i.within_budget,!0)}}var M=class extends Error{constructor(e){super(e),this.name="ChatParseError"}};function k(i){return typeof i=="string"&&i.length>0}function Xe(i){let e=String(i||"").toLowerCase();return e==="products"?"recommendation":e==="product_detail"?"product":e==="bundle"?"bundle":e==="escalation"?"escalation":"text"}function Je(i,e){let t=(n,s)=>{let r=Number(n);return Number.isFinite(r)?r:s};return{index:k(i==null?void 0:i.index)?Number(i.index):typeof(i==null?void 0:i.index)=="number"?i.index:e,documentTitle:k(i==null?void 0:i.document_title)?i.document_title:null,contentSnippet:k(i==null?void 0:i.content_snippet)?i.content_snippet:null,score:typeof i=="object"&&i!==null?t(i==null?void 0:i.score,null):null,rank:typeof i=="object"&&i!==null?t(i==null?void 0:i.rank,null):null}}var Y=class{static adapt(e){if(!e||typeof e!="object"||Array.isArray(e))throw new M("Chat response is not an object.");if(!k(e.response))throw new M("Chat response missing text.");let n=(Array.isArray(e.citations)?e.citations:[]).map((d,l)=>Je(d,l)).filter(d=>d.documentTitle!==null||d.contentSnippet!==null).slice(0,20),r=(Array.isArray(e.products)?e.products:[]).map(U).filter(d=>d!==null).slice(0,10),a=U(e.product,0),c=Ee(e.bundle);return{content:e.response,type:Xe(e.type),products:r,product:a,bundle:c,reference:k(e.reference)?e.reference:null,citations:n,conversationId:k(e.conversation_id)?e.conversation_id:null,confidenceScore:typeof e.confidence_score=="number"&&Number.isFinite(e.confidence_score)?e.confidence_score:null,metadata:{model:k(e.model)?e.model:null,provider:k(e.provider)?e.provider:null,latencyMs:typeof e.latency_ms=="number"?e.latency_ms:null,usage:e.usage&&typeof e.usage=="object"?{promptTokens:Number(e.usage.prompt_tokens)||0,completionTokens:Number(e.usage.completion_tokens)||0,totalTokens:Number(e.usage.total_tokens)||0,cost:Number(e.usage.cost)||0}:null}}}};var v=Object.freeze({PENDING:"pending",SENDING:"sending",SENT:"sent",ERROR:"error"}),Ze=0,E=class{constructor({role:e,content:t,citations:n=[],recommendations:s=[],type:r="text",products:a=[],product:c=null,bundle:d=null,reference:l=null}){this.id=`msg_${Date.now().toString(36)}_${Ze++}`,this.role=e,this.content=t,this.citations=n,this.recommendations=s,this.type=r,this.products=a,this.product=c,this.bundle=d,this.reference=l,this.status=v.SENT,this.retryable=!1,this.errorText=null,this.createdAt=new Date}markSending(){this.status=v.SENDING}markSent(){this.status=v.SENT}markError(e,t=!0){this.status=v.ERROR,this.errorText=e,this.retryable=t}isPending(){return this.status===v.PENDING||this.status===v.SENDING}};var Ce=4e3;function Qe(i){if(i==null)return{valid:!1,error:"Please type a message.",value:""};let e=V(i).trim();return e.length===0?{valid:!1,error:"Please type a message.",value:""}:e.length>Ce?{valid:!1,error:`Message is too long (maximum ${Ce} characters).`,value:e}:{valid:!0,error:null,value:e}}var X=class{constructor({apiClient:e,authManager:t,conversation:n,config:s}){this.apiClient=e,this.authManager=t,this.conversation=n,this.config=s,this._inFlight=null}get providerName(){return this.config.providerName}async sendMessage(e,t={}){let n=Qe(e);if(!n.valid)throw new Error(n.error);return this._inFlight?this._inFlight:(this._inFlight=this._send(n.value,t).finally(()=>{this._inFlight=null}),this._inFlight)}async _send(e,t){await this.authManager.ensureToken();let n={message:e,conversation_id:this.conversation.id},s=this._resolveCustomerId(t.customerId);s&&(n.customer_id=s);let{data:r}=await this.apiClient.post("/api/v1/widget/chat",n,{auth:!0,query:{provider_name:this.providerName}}),a;try{a=Y.adapt(r)}catch(d){throw d instanceof M?new Error("The assistant returned an unreadable response."):d}return this.conversation.updateFromResponse(a.conversationId),{message:new E({role:"assistant",content:a.content,citations:a.citations,type:a.type,products:a.products,product:a.product,bundle:a.bundle,reference:a.reference}),type:a.type,confidenceScore:a.confidenceScore,conversationId:a.conversationId}}_resolveCustomerId(e){let t=e!=null?e:this.config.customerId;return typeof t=="string"&&t.trim().length>0?t.trim().slice(0,256):null}get hasInFlightRequest(){return this._inFlight!==null}};var D=class extends Error{constructor(e){super(e),this.name="RecommendationParseError"}};function ke(i){return typeof i=="string"&&i.length>0?i:null}function J(i,e=null){if(i==null||i==="")return e;let t=Number(i);return Number.isFinite(t)?t:e}var Z=class{static adapt(e){if(!e||typeof e!="object"||Array.isArray(e))throw new D("Recommendation response is not an object.");if(!ke(e.query))throw new D("Recommendation response missing query.");let n=(Array.isArray(e.products)?e.products:[]).map(U).filter(s=>s!==null);return{query:e.query,rationale:ke(e.rationale),totalCount:J(e.total_count,n.length),type:"recommendation",budget:J(e.budget,null),discountAvailable:e.discount_available===!0,discount:J(e.discount,0),finalPrice:J(e.final_price,null),products:n}}};var Ae=2e3;function et(i){if(i==null)return{valid:!1,error:"Please type a message.",value:""};let e=V(i).trim();return e.length===0?{valid:!1,error:"Please type a message.",value:""}:e.length>Ae?{valid:!1,error:`Message is too long (maximum ${Ae} characters).`,value:e}:{valid:!0,error:null,value:e}}var Q=class{constructor({apiClient:e,authManager:t,config:n}){this.apiClient=e,this.authManager=t,this.config=n}async getRecommendations(e,t=null){let n=et(e);if(!n.valid)throw new Error(n.error);await this.authManager.ensureToken();let s={message:n.value},r=t!=null?String(t).trim():this.config.customerId;r&&(s.customer_id=r.slice(0,256));let{data:a}=await this.apiClient.post("/api/v1/widget/recommendations",s,{auth:!0}),c;try{c=Z.adapt(a)}catch(d){throw d instanceof D?new Error("The store returned unreadable recommendations."):d}return{view:c,raw:c}}};var ee=class{constructor({apiClient:e,authManager:t}){this.apiClient=e,this.authManager=t}async record({event:e,bundleKey:t=null,productIds:n=[],promoCode:s=null,discountPct:r=null,conversationId:a=null}){try{await this.authManager.ensureToken();let c={event:e};t&&(c.bundle_key=t),Array.isArray(n)&&n.length>0&&(c.product_ids=n.slice(0,50)),s&&(c.promo_code=s),r!==null&&Number.isFinite(Number(r))&&(c.discount_pct=Number(r)),a&&(c.conversation_id=a);let{data:d}=await this.apiClient.post("/api/v1/widget/bundles/events",c,{auth:!0});return d&&d.recorded===!0}catch{return!1}}};var tt="This assistant is not available for this store.",Se="Unable to initialize the store assistant.",it="The assistant is temporarily unavailable. Please try again shortly.",Ie="Unable to connect to the assistant.",nt="Too many requests. Please wait a moment and try again.",st="Your AI assistant session expired. Reconnecting...",rt="You've reached today's assistant message limit. Please try again later.",at="This store's AI assistant is temporarily unavailable.",z="Something went wrong. Please try again.";function ue(i,e={}){let{isBootstrap:t=!1}=e;if(i&&typeof i=="object"&&i.name==="ApiError"){let s=i.status,r=i.retryAfterSeconds,a=i.detail&&typeof i.detail=="string"?i.detail.toLowerCase():"";if(s===401)return{message:t?Se:st,kind:"auth",retryable:!t,retryAfterSeconds:null,rateLimit:i.rateLimitHeaders()};if(s===403)return{message:tt,kind:"disabled",retryable:!1,retryAfterSeconds:null,rateLimit:i.rateLimitHeaders()};if(s===404)return{message:t?Se:z,kind:"not_found",retryable:!1,retryAfterSeconds:null,rateLimit:i.rateLimitHeaders()};if(s===422||s===400)return{message:z,kind:"invalid_request",retryable:!1,retryAfterSeconds:null,rateLimit:i.rateLimitHeaders()};if(s===409)return{message:z,kind:"conflict",retryable:!1,retryAfterSeconds:null,rateLimit:i.rateLimitHeaders()};if(s===429)return a.includes("quota")||a.includes("token")?{message:at,kind:"quota",retryable:!1,retryAfterSeconds:r,rateLimit:i.rateLimitHeaders()}:a.includes("daily")||a.includes("consumer")?{message:rt,kind:"consumer_limit",retryable:!1,retryAfterSeconds:r,rateLimit:i.rateLimitHeaders()}:{message:nt,kind:"rate_limited",retryable:!0,retryAfterSeconds:r,rateLimit:i.rateLimitHeaders()};if(s!==null&&s>=500)return{message:it,kind:"server_error",retryable:!0,retryAfterSeconds:null,rateLimit:i.rateLimitHeaders()};if(i.kind===w.TIMEOUT)return{message:Ie,kind:"timeout",retryable:!0,retryAfterSeconds:null,rateLimit:i.rateLimitHeaders()};if(i.kind===w.NETWORK)return{message:Ie,kind:"network",retryable:!0,retryAfterSeconds:null,rateLimit:i.rateLimitHeaders()}}let n=i&&typeof i=="object"&&typeof i.message=="string"&&i.message.length>0?i.message:z;return{message:n.length>500?z:n,kind:"unknown",retryable:!1,retryAfterSeconds:null,rateLimit:null}}var te=class{constructor(){this._conversationId=null,this._startedAt=Date.now(),this._storageKey=null}get id(){return this._conversationId}setStorageKey(e){this._storageKey=e,this._restore()}setId(e){this._conversationId=e}updateFromResponse(e){typeof e=="string"&&e.length>0&&(this._conversationId=e,this._persist())}reset(){this._conversationId=null,this._startedAt=Date.now(),this._persist()}_restore(){if(!this._storageKey)return;try{let e=sessionStorage.getItem(this._storageKey);typeof e=="string"&&e.length>0&&(this._conversationId=e)}catch{}}_persist(){if(!this._storageKey)return;try{this._conversationId?sessionStorage.setItem(this._storageKey,this._conversationId):sessionStorage.removeItem(this._storageKey)}catch{}}};function o(i,e,t={},n=[]){let s=i.createElement(e);for(let[r,a]of Object.entries(t))a==null||a===!1||(r==="class"?s.className=a:r.startsWith("on")&&typeof a=="function"?s.addEventListener(r.slice(2).toLowerCase(),a):r==="dataset"?Object.assign(s.dataset,a):s.setAttribute(r,a===!0?"":String(a)));for(let r of n)r instanceof Node?s.appendChild(r):r!=null&&s.appendChild(i.createTextNode(String(r)));return s}function Te(i){for(;i.firstChild;)i.removeChild(i.firstChild)}function y(i,e){var t;for(;i.firstChild;)i.removeChild(i.firstChild);i.appendChild((t=i.ownerDocument)==null?void 0:t.createTextNode(String(e)))}function he(i){let e=["button:not([disabled])","[href]","input:not([disabled])","textarea:not([disabled])","select:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");return[...i.querySelectorAll(e)].filter(t=>{let n=t.ownerDocument.defaultView.getComputedStyle(t);return n&&n.visibility!=="hidden"&&n.display!=="none"})}var ie=class{constructor(e,t){this.shadowRoot=e,this.doc=t,this.root=o(t,"div",{class:"widget-root"}),e.appendChild(this.root),this.launcherSlot=o(t,"div",{class:"launcher-slot"}),this.panelSlot=o(t,"div",{class:"panel-slot"}),this.root.appendChild(this.launcherSlot),this.root.appendChild(this.panelSlot)}mountLauncher(e){this.launcherSlot.appendChild(e)}mountPanel(e){this.panelSlot.appendChild(e)}focusElement(e){e&&typeof e.focus=="function"&&e.focus()}};var ot={chatBubble:{viewBox:"0 0 24 24",path:"M12 3C6.48 3 2 6.94 2 11.8c0 2.66 1.3 5.04 3.4 6.62-.2 1.42-.94 3.1-1.94 4.08-.13.13-.04.35.14.36 1.52.1 3.24-.46 4.5-1.3.9.22 1.87.34 2.9.34 5.52 0 10-3.94 10-8.8S17.52 3 12 3z"},close:{viewBox:"0 0 24 24",path:"M18.3 5.71 12 12l6.3 6.29a1 1 0 1 1-1.42 1.42L12 13.41l-6.29 6.3a1 1 0 0 1-1.42-1.42L10.59 12 4.29 5.71a1 1 0 0 1 1.42-1.42L12 10.59l6.29-6.3a1 1 0 1 1 1.42 1.42z"},sparkle:{viewBox:"0 0 24 24",path:"M12 2l1.8 5.6L19.4 9.4l-5.6 1.8L12 16.8l-1.8-5.6L4.6 9.4l5.6-1.8L12 2zM19 14l.9 2.6L22.5 17.5l-2.6.9L19 21l-.9-2.6-2.6-.9 2.6-.9L19 14zM5 15l.7 2 2 .7-2 .7L5 20.4l-.7-2-2-.7 2-.7L5 15z"},plus:{viewBox:"0 0 24 24",path:"M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5z"},send:{viewBox:"0 0 24 24",path:"M3.4 20.4 20.85 12 3.4 3.6 3.4 10l12 2-12 2 0 6.4z"},chevronLeft:{viewBox:"0 0 24 24",path:"M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z"},chevronRight:{viewBox:"0 0 24 24",path:"M8.59 16.59 10 18l6-6-6-6-1.41 1.41L13.17 12z"},star:{viewBox:"0 0 24 24",path:"M12 2l2.92 6.26 6.88.6-5.2 4.53 1.55 6.72L12 16.9 5.85 20.1l1.55-6.72-5.2-4.53 6.88-.6L12 2z"},arrowRight:{viewBox:"0 0 24 24",path:"M13.17 5.59 11.76 7l4.41 4.41H4v2h12.17l-4.41 4.41 1.41 1.42L20.01 13l-6.84-7.41z"},copy:{viewBox:"0 0 24 24",path:"M16 1H4a2 2 0 0 0-2 2v14h2V3h12V1zm3 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h11v14z"},check:{viewBox:"0 0 24 24",path:"M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"},cart:{viewBox:"0 0 24 24",path:"M7 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM7.17 14.75l.03-.12.9-1.63h7.45a2 2 0 0 0 1.75-1.02L21.94 5H5.21l-.94-2H1v2h2l3.6 7.59-1.35 2.44A2 2 0 0 0 7 17h12v-2H7.42c-.14 0-.25-.11-.25-.25z"}};function g(i,e,t={}){let n=typeof e=="string"?ot[e]:e,s="http://www.w3.org/2000/svg",r=i.createElementNS(s,"svg");r.setAttribute("viewBox",n.viewBox),r.setAttribute("aria-hidden","true");for(let[c,d]of Object.entries(t))d!=null&&d!==!1&&r.setAttribute(c,String(d));let a=i.createElementNS(s,"path");return a.setAttribute("d",n.path),r.appendChild(a),r}var Ne={"aria-label":"Show AI assistant","aria-controls":"ac-widget-panel"},ne=class{constructor(e,{onClick:t}){this.doc=e,this.onClick=t,this.button=o(e,"button",{type:"button",class:"launcher","aria-label":Ne["aria-label"],"aria-expanded":"false","aria-controls":Ne["aria-controls"],"aria-haspopup":"dialog",onclick:r=>{this.onClick(r)}});let n=o(e,"span",{class:"launcher-open-svg"});n.appendChild(g(e,"chatBubble",{class:"launcher-svg"}));let s=o(e,"span",{class:"launcher-close-svg"});s.appendChild(g(e,"close",{class:"launcher-svg"})),this.button.appendChild(n),this.button.appendChild(s)}setExpanded(e){this.button.setAttribute("aria-expanded",String(e))}get element(){return this.button}};var se=class{static create(e,t){var r;let n=Array.isArray(t)?t.filter(a=>a&&typeof a=="object"):[];if(n.length===0)return null;let s=o(e,"div",{class:"citations",role:"group"});s.appendChild(o(e,"div",{class:"citations-title"},["Sources"]));for(let a of n){let c=o(e,"div",{class:"citation"}),d=o(e,"span",{class:"citation-index"});y(d,String((r=a.index)!=null?r:"\u2022")),c.appendChild(d);let l=o(e,"div",{});a.documentTitle&&l.appendChild(o(e,"div",{class:"citation-title"},[a.documentTitle])),a.contentSnippet&&l.appendChild(o(e,"div",{class:"citation-snippet"},[a.contentSnippet])),c.appendChild(l),s.appendChild(c)}return s}};var lt={USD:"$",CAD:"$",AUD:"$",NZD:"$",SGD:"$",HKD:"$",EUR:"\u20AC",GBP:"\xA3",JPY:"\xA5"};function A(i,e=null){if(i==null)return"";let t=String(i).trim();if(t.length===0)return"";let n=e?lt[e.toUpperCase()]:null;return n?`${n}${t}`:e?`${e} ${t}`:t}function Re(i){if(i==null||!Number.isFinite(Number(i)))return"";let e=Number(i),t=Math.round(e*10)/10;return`${Number.isInteger(t)?t.toFixed(0):t.toFixed(1)}%`}var F=class{static create(e,t){let n=t.productUrl?T(t.productUrl,e):null,s;if(n?(n.classList.add("recommendation-card"),n.setAttribute("aria-label",t.title?`View ${t.title} in the store`:"View product in the store"),s=n):s=o(e,"div",{class:"recommendation-card"}),t.imageUrl&&T(t.imageUrl,e)){let l=e.createElement("img");l.className="recommendation-image",l.loading="lazy",l.alt=t.title?`Image of ${t.title}`:"Product image",l.src=t.imageUrl,l.addEventListener("error",()=>l.remove()),s.appendChild(l)}else s.appendChild(o(e,"div",{class:"recommendation-image"}));let r=o(e,"div",{class:"recommendation-body"});if(t.title&&r.appendChild(o(e,"div",{class:"recommendation-title"},[t.title])),t.rating!==null&&t.rating!==void 0){let l=o(e,"div",{class:"recommendation-rating"});l.appendChild(g(e,"star",{class:"rating-icon"}));let u=Number(t.rating),p=`${Number.isFinite(u)?u.toFixed(1):t.rating} out of 5`;l.appendChild(o(e,"span",{class:"rating-value"},[p])),r.appendChild(l)}let a=o(e,"div",{class:"recommendation-price-row"}),c=A(t.originalPrice||t.price,t.currency),d=A(t.discountedPrice,t.currency);if(d&&d!==c){let l=o(e,"span",{class:"price-original"});y(l,c),a.appendChild(l);let u=o(e,"span",{class:"price-final"});y(u,d),a.appendChild(u)}else if(c){let l=o(e,"span",{class:"recommendation-price"});y(l,c),a.appendChild(l)}if(t.discountPct!==null&&t.discountPct!==void 0&&Number(t.discountPct)>0){let l=o(e,"span",{class:"discount-badge"}),u=Number(t.discountPct);y(l,`-${Number.isInteger(u)?u:u.toFixed(1)}%`),a.appendChild(l)}if(a.childNodes.length>0&&r.appendChild(a),t.inStock!==null&&t.inStock!==void 0&&r.appendChild(o(e,"span",{class:`availability-badge ${t.inStock?"in-stock":"out-of-stock"}`},[t.inStock?"In stock":"Out of stock"])),Array.isArray(t.matchReasons)&&t.matchReasons.length>0){let l=o(e,"div",{class:"recommendation-reasons"});for(let u of t.matchReasons.slice(0,6))l.appendChild(o(e,"span",{class:"reason-badge"},[u]));r.appendChild(l)}if(n){let l=o(e,"span",{class:"recommendation-cta"});l.appendChild(o(e,"span",{},["View Product"])),l.appendChild(g(e,"arrowRight",{class:"cta-icon"})),r.appendChild(l)}return s.appendChild(r),s}static list(e,t,n={}){let s=Array.isArray(t)?t.filter(p=>p&&typeof p=="object"):[];if(s.length===0)return null;let r=o(e,"div",{class:"recommendations",role:"group"});if(r.appendChild(o(e,"div",{class:"recommendations-title"},[n.title||"Recommended for you"])),n.rationale){let p=o(e,"div",{class:"recommendations-rationale"});y(p,n.rationale),r.appendChild(p)}let a=o(e,"div",{class:"recommendations-scroller",tabindex:"0","aria-label":"Product recommendations"});for(let p of s.slice(0,8))a.appendChild(this.create(e,p));let c=o(e,"div",{class:"recommendations-controls"}),d=p=>{let b=a.querySelector(".recommendation-card"),f=b?b.getBoundingClientRect().width+10:260;a.scrollBy({left:p*f,behavior:"smooth"})},l=o(e,"button",{type:"button",class:"carousel-arrow","aria-label":"Previous recommendations",onclick:()=>d(-1)});l.appendChild(g(e,"chevronLeft",{class:"carousel-arrow-icon"}));let u=o(e,"button",{type:"button",class:"carousel-arrow","aria-label":"Next recommendations",onclick:()=>d(1)});return u.appendChild(g(e,"chevronRight",{class:"carousel-arrow-icon"})),c.appendChild(l),c.appendChild(u),a.addEventListener("keydown",p=>{p.key==="ArrowLeft"?(p.preventDefault(),d(-1)):p.key==="ArrowRight"&&(p.preventDefault(),d(1))}),r.appendChild(a),r.appendChild(c),r}};var re=class i{static create(e,t,n={}){let s=o(e,"div",{class:"bundle-card",role:"group","aria-label":"Bundle offer"});if(Array.isArray(t.items)&&t.items.length>0){let l=o(e,"div",{class:"bundle-items"});for(let u of t.items)if(u.productUrl&&T(u.productUrl,e)){let p=T(u.productUrl,e);p.className="bundle-item-link";let b=o(e,"span",{class:"bundle-item-name"},[u.title||"Product"]),f=o(e,"span",{class:"bundle-item-price"});y(f,A(u.priceAfterDiscount||u.originalPrice,t.currency)),p.appendChild(b),f.textContent&&p.appendChild(f),l.appendChild(p)}else{let p=o(e,"div",{class:"bundle-item"}),b=o(e,"span",{class:"bundle-item-name"},[u.title||"Product"]);p.appendChild(b);let f=o(e,"span",{class:"bundle-item-price"});y(f,A(u.priceAfterDiscount||u.originalPrice,t.currency)),f.textContent&&p.appendChild(f),l.appendChild(p)}s.appendChild(l)}let r=o(e,"div",{class:"bundle-totals"}),a=(l,u,p="")=>{let b=o(e,"div",{class:"bundle-total-row"});return b.appendChild(o(e,"span",{class:"bundle-total-label"},[l])),b.appendChild(o(e,"span",{class:`bundle-total-value ${p}`},[u])),b};t.totalOriginal&&r.appendChild(a("Bundle",A(t.totalOriginal,t.currency),"bundle-total-original")),t.discountPct!==null&&t.discountPct!==void 0&&Number(t.discountPct)>0&&r.appendChild(a("Discount",Re(t.discountPct),"bundle-total-discount")),t.finalTotal&&r.appendChild(a("Final",A(t.finalTotal,t.currency),"bundle-total-final")),r.childNodes.length>0&&s.appendChild(r);let c=o(e,"div",{class:"bundle-actions"});if(t.promoCode){let l=o(e,"button",{type:"button",class:"action-button bundle-copy-button",onclick:()=>this._copyOffer(e,l,t,n)});l.appendChild(g(e,"copy",{class:"bundle-action-icon"})),l.appendChild(o(e,"span",{class:"bundle-copy-label"},["Copy Offer"])),c.appendChild(l)}let d=i._shopUrl(t);if(d){let l=T(d,e);l&&(l.className="action-button bundle-shop-button",l.appendChild(g(e,"cart",{class:"bundle-action-icon"})),l.appendChild(o(e,"span",{},["Shop Bundle"])),l.addEventListener("click",()=>{typeof n.onTrack=="function"&&n.onTrack({event:"bundle_clicked",productIds:i._productIds(t),promoCode:t.promoCode,discountPct:t.discountPct,bundleKey:t.promoCode?`promo:${t.promoCode}`:null})}),c.appendChild(l))}return c.childNodes.length>0&&s.appendChild(c),s}static _shopUrl(e){if(!Array.isArray(e.items))return null;for(let t of e.items)if(t.productUrl)return t.productUrl;return null}static _productIds(e){return Array.isArray(e.items)?e.items.map(t=>t.id).filter(Boolean):[]}static async _copyOffer(e,t,n,s){let r=n.promoCode;if(!r)return;let a=!1;try{let l=e.defaultView?e.defaultView.navigator:typeof navigator!="undefined"?navigator:null;l&&l.clipboard&&l.clipboard.writeText&&(await l.clipboard.writeText(r),a=!0)}catch{a=!1}if(!a)try{let l=e.createElement("textarea");l.value=r,l.setAttribute("readonly",""),l.style.position="fixed",l.style.opacity="0",e.body.appendChild(l),l.select(),a=e.execCommand&&e.execCommand("copy"),e.body.removeChild(l)}catch{a=!1}typeof s.onTrack=="function"&&s.onTrack({event:"promo_copied",productIds:i._productIds(n),promoCode:r,discountPct:n.discountPct,bundleKey:`promo:${r}`});let c=t.querySelector(".bundle-copy-label"),d=t.querySelector(".bundle-action-icon");if(c&&y(c,a?"Copied!":"Copy Offer"),d&&a){let l=g(e,"check",{class:"bundle-action-icon"});d.parentNode.replaceChild(l,d)}a&&setTimeout(()=>{let l=t.querySelector(".bundle-copy-label");l&&y(l,"Copy Offer")},2e3)}};var H=class{static create(e,t,n={}){let s=t.role==="user",r=o(e,"div",{class:`bubble-row ${s?"user":"assistant"}`,"data-message-id":t.id}),a=o(e,"div",{class:"bubble-column"}),c=o(e,"div",{class:`bubble ${s?"user":"assistant"} ${t.status===v.ERROR?"bubble-error":""} ${!s&&t.type==="escalation"?"bubble-escalation":""}`});if(t.status===v.ERROR&&t.errorText){if(y(c,t.errorText),a.appendChild(c),t.retryable&&n.onRetry){let d=o(e,"div",{class:"retry-row"});d.appendChild(o(e,"button",{type:"button",class:"action-button",onclick:()=>n.onRetry(t)},["Retry"])),a.appendChild(d)}}else{if(y(c,t.content||""),a.appendChild(c),!s&&t.type==="escalation"&&a.appendChild(this._escalationNotice(e)),!s&&t.citations&&t.citations.length>0){let d=se.create(e,t.citations);d&&a.appendChild(d)}if(!s&&(t.type==="recommendation"||t.recommendations.length>0)){let d=t.products&&t.products.length>0?t.products:t.recommendations,l=t.reference&&t.reference!==t.content?t.reference:null,u=F.list(e,d,{rationale:l});u&&a.appendChild(u)}else if(!s&&t.type==="product"&&t.product){let d=F.list(e,[t.product]);d&&a.appendChild(d)}if(!s&&t.type==="bundle"&&t.bundle){let d=re.create(e,t.bundle,{onTrack:n.onTrackBundle,getConversationId:n.getConversationId});a.appendChild(d)}!s&&n.canShowRecommendations&&n.onShowRecommendations&&!(t.recommendations&&t.recommendations.length>0)&&t.type!=="bundle"&&t.type!=="product"&&a.appendChild(o(e,"button",{type:"button",class:"action-button",onclick:()=>n.onShowRecommendations(t)},["Get product recommendations"]))}return r.appendChild(a),r}static _escalationNotice(e){let t=o(e,"div",{class:"escalation-notice",role:"status"});return t.appendChild(g(e,"sparkle",{class:"escalation-icon"})),t.appendChild(o(e,"span",{},["Your request has been escalated to our human support team."])),t}};var ae=class{static create(e){let t=o(e,"span",{class:"typing","aria-label":"The assistant is typing",role:"status"});for(let n=0;n<3;n+=1)t.appendChild(o(e,"span",{class:"typing-dot"}));return o(e,"div",{class:"bubble-row assistant",role:"presentation"},[o(e,"div",{class:"bubble assistant"},[t])])}};var oe=class{constructor(e){this.doc=e,this.element=o(e,"div",{class:"message-area",role:"log","aria-live":"polite","aria-label":"Chat messages"}),this._typing=null,this._callbacks={},this._stickToBottom=!0,this.element.addEventListener("scroll",()=>{let{scrollTop:t,scrollHeight:n,clientHeight:s}=this.element;this._stickToBottom=n-t-s<40})}setCallbacks(e){this._callbacks=e}clear(){Te(this.element),this._typing=null,this._stickToBottom=!0}showWelcome(e){let t=o(this.doc,"div",{class:"welcome-message"});t.textContent=e,this.element.appendChild(t)}appendMessage(e){let t=H.create(this.doc,e,this._callbacks);return this.element.appendChild(t),this._scrollToBottom(),t}replaceMessage(e){let t=this.element.querySelector(`[data-message-id="${CSS.escape(e.id)}"]`);t&&t.parentNode&&(t.parentNode.replaceChild(H.create(this.doc,e,this._callbacks),t),this._scrollToBottom())}showTyping(){this._typing||(this._typing=ae.create(this.doc),this.element.appendChild(this._typing),this._scrollToBottom())}hideTyping(){this._typing&&this._typing.parentNode&&this._typing.parentNode.removeChild(this._typing),this._typing=null}showState(e,t){let n=o(this.doc,"div",{class:"state-box",role:"status"});return e&&n.appendChild(o(this.doc,"div",{class:"state-box-title"},[e])),t&&n.appendChild(o(this.doc,"div",{class:"state-box-text"},[t])),this.element.appendChild(n),n}_scrollToBottom(){this._stickToBottom&&(this.element.scrollTop=this.element.scrollHeight)}};var le=class{constructor(e,{onSend:t}){this.doc=e,this.onSend=t,this._disabled=!1,this.bar=o(e,"div",{class:"input-bar"}),this.textarea=o(e,"textarea",{class:"input-textarea",rows:1,"aria-label":"Message the assistant",placeholder:"Ask me anything..."}),this.sendButton=o(e,"button",{type:"button",class:"send-button","aria-label":"Send message"}),this.sendButton.appendChild(g(e,"send")),this.sendButton.disabled=!0,this.textarea.addEventListener("input",()=>{this._autoResize()}),this.textarea.addEventListener("keydown",n=>{n.key==="Enter"&&!n.shiftKey&&(n.preventDefault(),this.submit())}),this.sendButton.addEventListener("click",()=>this.submit()),this.textarea.addEventListener("input",()=>{this.sendButton.disabled=this._disabled||this.textarea.value.trim().length===0}),this.bar.appendChild(this.textarea),this.bar.appendChild(this.sendButton)}get element(){return this.bar}setDisabled(e){this._disabled=e,this.textarea.disabled=e,this.sendButton.disabled=e||this.textarea.value.trim().length===0}isDisabled(){return this._disabled}submit(){if(this._disabled)return;let e=this.textarea.value.trim();e&&(this.textarea.value="",this._autoResize(),this.sendButton.disabled=!0,this.onSend(e))}focus(){this.textarea.focus()}_autoResize(){this.textarea.style.height="auto",this.textarea.style.height=`${Math.min(120,Math.max(40,this.textarea.scrollHeight))}px`}};var j=class{static create(e,{title:t,message:n,retryable:s=!1,onRetry:r}){let a=o(e,"div",{class:"state-box",role:"alert"});if(t&&a.appendChild(o(e,"div",{class:"state-box-title"},[t])),n&&a.appendChild(o(e,"div",{class:"state-box-text"},[n])),s&&r){let c=o(e,"button",{type:"button",class:"action-button",onclick:r},["Retry"]);c.style.marginTop="12px",a.appendChild(c)}return a}};var ce=class{constructor(e,t,n){this.doc=e,this.title=t.title,this.welcomeMessage=t.welcomeMessage,this.callbacks=n,this.messages=new oe(e),this.messages.setCallbacks(n.messageHandlers),this.input=new le(e,{onSend:n.onSend}),this.hint=o(e,"div",{class:"input-hint",role:"status",hidden:!0}),this.element=this._build(),this._firstOpen=!0,this._open=!1}_build(){let e=o(this.doc,"div",{class:"panel",id:"ac-widget-panel"}),t=o(this.doc,"div",{class:"panel-header"}),n=o(this.doc,"div",{class:"panel-header-avatar"});n.appendChild(g(this.doc,"sparkle")),t.appendChild(n),t.appendChild(o(this.doc,"div",{class:"panel-header-title"},[this.title]));let s=o(this.doc,"div",{class:"panel-header-actions"}),r=o(this.doc,"button",{type:"button",class:"icon-button","aria-label":"Start a new conversation",onclick:()=>this.callbacks.onNewChat()});r.appendChild(g(this.doc,"plus"));let a=o(this.doc,"button",{type:"button",class:"icon-button","aria-label":"Close assistant",onclick:()=>this.callbacks.onClose()});return a.appendChild(g(this.doc,"close")),s.appendChild(r),s.appendChild(a),t.appendChild(s),e.appendChild(t),e.appendChild(this.messages.element),e.appendChild(this.hint),e.appendChild(this.input.element),e.addEventListener("keydown",c=>{c.key==="Tab"&&this._open&&c.target instanceof Node&&e.contains(c.target)&&this._trapTabFocus(c)}),e}_trapTabFocus(e){let t=he(this.element);if(t.length===0)return;let n=t[0],s=t[t.length-1];e.shiftKey&&(e.target===n||!ct(this.element,e.target))?(e.preventDefault(),s.focus()):!e.shiftKey&&e.target===s&&(e.preventDefault(),n.focus())}open(){this._open=!0,this.element.classList.add("is-open"),this.element.setAttribute("aria-hidden","false"),this._firstOpen&&(this._firstOpen=!1,this.input.focus())}close(){this._open=!1,this.element.classList.remove("is-open"),this.element.setAttribute("aria-hidden","true")}get isOpen(){return this._open}get lastFocusable(){let e=he(this.element);return e.length>0?e[e.length-1]:null}focus(){this.input.focus()}showWelcome(){this.messages.showWelcome(this.welcomeMessage)}showTyping(){this.messages.showTyping()}hideTyping(){this.messages.hideTyping()}appendMessage(e){return this.messages.appendMessage(e)}replaceMessage(e){this.messages.replaceMessage(e)}clearMessages(){this.messages.clear()}showError({title:e,message:t,retryable:n,onRetry:s}){this.messages.clear(),this.messages.element.appendChild(j.create(this.doc,{title:e,message:t,retryable:n,onRetry:s})),this.input.setDisabled(!0)}showStatus(e,t){this.messages.clear(),this.messages.element.appendChild(j.create(this.doc,{title:e,message:t,retryable:!1}))}async showRateLimit(e){this.input.setDisabled(!0);let t=Math.max(0,Math.floor(e||0)),n=()=>{if(t<=0){this.hint.hidden=!0,this.input.setDisabled(!1);return}this.hint.hidden=!1,this.hint.textContent=`Too many requests. Retry in ${t}s.`,t-=1,this._rateLimitTimer=setTimeout(n,1e3)};n()}clearRateLimit(){this._rateLimitTimer&&(clearTimeout(this._rateLimitTimer),this._rateLimitTimer=null),this.hint.hidden=!0}setInputDisabled(e){this.input.setDisabled(e)}};function ct(i,e){return i.contains(e)}var N="ai-commerce-widget",dt="ai-commerce-widget",pt=.3,ut="If you need more help, contact the store for human support.";function ht(){return typeof crypto!="undefined"&&crypto.randomUUID?crypto.randomUUID():`s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,10)}`}var G=class extends HTMLElement{static get observedAttributes(){return["data-widget-key","data-api-base-url","data-provider-name","data-position","data-title","data-welcome-message","data-theme","data-accent-color","data-customer-id","data-debug"]}constructor(){super(),this.attachShadow({mode:"open"}),this._config=null,this._state=new W(h.INITIALIZING),this._conversation=new te,this._conversation.setStorageKey("ac:conv:"+String((this.dataset&&this.dataset.widgetKey)||"").trim()),this._messages=[],this._sessionId=ht(),this._initialized=!1,this._bootstrapAttempted=!1,this._recommendationsEnabled=!1,this._chatEnabled=!1,this._onStateChange=this._onStateChange.bind(this)}connectedCallback(){if(this._initialized)return;this._initialized=!0;let e=document.createElement("style");e.textContent=xe,this.shadowRoot.appendChild(e),this._shell=new ie(this.shadowRoot,this.ownerDocument),this._state.subscribe(this._onStateChange),this._init()}_init(){try{this._config=this._readConfig(),this._applyHostAttributes(this._config)}catch(e){this._fatalConfigError(e);return}this._state.set(h.READY),this._renderLauncher(),this._ensureApi(),this._auth.seedFromSlot(),this._config.autoOpen&&this.open()}_readConfig(){let e=this.dataset;return{widgetKey:(e.widgetKey||"").trim(),apiBaseUrl:(e.apiBaseUrl||"").trim().replace(/\/+$/,""),providerName:(e.providerName||"openai").trim(),title:(e.title||"AI Commerce Assistant").slice(0,80),welcomeMessage:(e.welcomeMessage||"Hi, I can help you with questions about this store. What would you like to know?").slice(0,500),position:e.position==="left"?"left":"right",theme:e.theme==="dark"?"dark":"light",accentColor:/^#[0-9a-fA-F]{3,8}$/.test(e.accentColor||"")?e.accentColor:null,customerId:(e.customerId||"").trim().slice(0,256)||null,autoOpen:e.autoOpen==="true"||e.autoOpen==="1",debug:e.debug==="true"||e.debug==="1"}}_applyHostAttributes(e){if(this.setAttribute("data-position",e.position),e.accentColor&&(this.style.setProperty("--ac-widget-primary",e.accentColor),this.style.setProperty("--ac-widget-primary-hover",e.accentColor),this.style.setProperty("--ac-widget-user-bubble",e.accentColor)),e.theme==="dark"){this.setAttribute("data-theme","dark");for(let[t,n]of Object.entries({"--ac-widget-bg":"#111827","--ac-widget-text":"#f3f4f6","--ac-widget-text-secondary":"#9ca3af","--ac-widget-border":"#374151","--ac-widget-assistant-bubble":"#1f2937"}))this.style.setProperty(t,n)}}_fatalConfigError(e){this._state.set(h.AUTHENTICATION_FAILED),(this.dataset.debug==="true"||this.dataset.debug==="1")&&console.info("[ai-commerce-widget] configuration error",e==null?void 0:e.message)}_renderLauncher(){this._launcher=new ne(this.ownerDocument,{onClick:()=>this.toggle()}),this._shell.mountLauncher(this._launcher.element)}_ensurePanel(){return this._panel?this._panel:(this._panel=new ce(this.ownerDocument,{title:this._config.title,welcomeMessage:this._config.welcomeMessage},{onClose:()=>this.close(),onNewChat:()=>this.startNewConversation(),onSend:e=>this._handleSend(e),messageHandlers:{onRetry:e=>this._retryMessage(e),canShowRecommendations:()=>this._recommendationsEnabled,onShowRecommendations:e=>this._showRecommendations(e),onTrackBundle:e=>this._trackBundleEvent(e),getConversationId:()=>this._conversation.id}}),this._shell.mountPanel(this._panel.element),this._panel.element.addEventListener("keydown",e=>{e.key==="Escape"&&(e.preventDefault(),this.close())}),this._panel)}_ensureApi(){return this._api?this._api:(this._auth=new K({widgetKey:this._config.widgetKey,apiClient:new P({baseUrl:this._config.apiBaseUrl})}),this._api=new P({baseUrl:this._config.apiBaseUrl,getToken:()=>this._auth.getToken(),bootstrap:()=>this._auth.refresh()}),this._chat=new X({apiClient:this._api,authManager:this._auth,conversation:this._conversation,config:{providerName:this._config.providerName,customerId:this._config.customerId}}),this._recommendations=new Q({apiClient:this._api,authManager:this._auth,config:{customerId:this._config.customerId}}),this._bundleEvents=new ee({apiClient:this._api,authManager:this._auth}),this._api)}get state(){return this._state.state}get conversationId(){return this._conversation.id}async open(){this._panel||this._ensurePanel(),this._state.set(h.OPENING),this._panel.open(),this._panel.showWelcome(),this._launcher.setExpanded(!0),this._panel.focus(),await this._bootstrapIfNeeded(),this._state.set(h.READY)}close(){this._panel&&(this._panel.close(),this._panel.clearRateLimit()),this._launcher&&(this._launcher.setExpanded(!1),this._launcher.element.focus()),this._state.set(h.READY),this._emit("closed")}toggle(){this._panel&&this._panel.isOpen?this.close():this.open()}startNewConversation(){this._conversation.reset(),this._messages=[],this._panel.clearMessages(),this._panel.showWelcome(),this._panel.setInputDisabled(!1),this._panel.clearRateLimit()}async _bootstrapIfNeeded(){if(!(this._bootstrapAttempted&&this._auth&&!this._auth.isTokenExpired())){this._api||this._ensureApi(),this._bootstrapAttempted=!0;try{let e=this._auth.seedFromSlot()||(await this._auth.bootstrap());if(this._chatEnabled=e.configuration.chat,this._recommendationsEnabled=e.configuration.recommendations,this._emit("ready",{widgetId:e.widgetId,configuration:{chat:this._chatEnabled,recommendations:this._recommendationsEnabled}}),!this._chatEnabled&&!this._recommendationsEnabled){this._state.set(h.DISABLED),this._panel.showError({title:"Assistant unavailable",message:"This assistant is not available for this store."});return}!this._chatEnabled&&this._recommendationsEnabled&&this._panel.setInputDisabled(!0)}catch(e){this._handleBootstrapError(e)}}}_handleBootstrapError(e){let t=ue(e,{isBootstrap:!0});t.kind==="disabled"?this._state.set(h.DISABLED):this._state.set(h.AUTHENTICATION_FAILED),this._panel.showError({title:"Assistant unavailable",message:t.message,retryable:t.retryable,onRetry:t.retryable?()=>this._retryBootstrap():void 0})}_retryBootstrap(){this._auth&&this._auth.clearBootstrapError(),this._bootstrapAttempted=!1,this._panel.setInputDisabled(!0),this._panel.showStatus("Assistant","Reconnecting..."),this._bootstrapIfNeeded().finally(()=>{this._chatEnabled&&this._panel.setInputDisabled(!1)})}async _handleSend(e,t={}){var r,a;if(this._state.is(h.SENDING))return;this._panel&&this._panel.clearRateLimit();let n=t.existingMessage,s=n&&n.role==="user"?n:(()=>{let c=new E({role:"user",content:e});return c.markSending(),this._messages.push(c),this._panel.appendMessage(c),c})();s.markSending(),s.errorText=null,n&&this._panel.replaceMessage(s),this._state.set(h.SENDING),this._panel.setInputDisabled(!0),this._chat||this._ensureApi(),this._auth.hasToken||await this._bootstrapIfNeeded(),this._panel.showTyping(),this._emit("chat_started",{query:e});try{let c=await this._chat.sendMessage(e,{customerId:(r=t.customerId)!=null?r:null});s.markSent(),this._panel.replaceMessage(s);let d=c.message;if(this._messages.push(d),this._panel.appendMessage(d),c.confidenceScore!==null&&c.confidenceScore<pt){let l=new E({role:"assistant",content:ut});this._messages.push(l),this._panel.appendMessage(l)}this._emit("chat_done",{query:e,conversationId:(a=c.conversationId)!=null?a:null}),this._state.set(h.READY)}catch(c){s.markError(this._friendlyError(c),!0),this._panel.replaceMessage(s),this._emit("error",{error:this._friendlyError(c)}),this._applyMessageErrorState(c)}finally{this._panel.hideTyping(),this._panel.setInputDisabled(!1)}}_friendlyError(e){return e instanceof Error&&e.message&&!(e instanceof x)?e.message:ue(e).message}_trackBundleEvent(e){this._bundleEvents&&this._bundleEvents.record({...e,conversationId:this._conversation.id||null})}_applyMessageErrorState(e){var t;e instanceof x&&e.isRateLimited()?(this._state.set(h.RATE_LIMITED),this._panel.showRateLimit((t=e.retryAfterSeconds)!=null?t:10)):e instanceof x&&(e.status===403||e.status===404||e.status===422||e.status===400)?this._state.set(h.ERROR):e instanceof x&&e.status===401?this._state.set(h.ERROR):this._state.set(h.ERROR)}async _retryMessage(e){if(this._state.is(h.SENDING))return;let t=null;if(e.role==="user")t=e;else{let n=this._messages.findIndex(r=>r.id===e.id),s=n>0?this._messages[n-1]:null;s&&s.role==="user"&&(t=s)}!t||!t.content||await this._handleSend(t.content,{retry:!0,existingMessage:t})}async _showRecommendations(e){if(!this._recommendationsEnabled||this._state.is(h.SENDING))return;let t=this._messages.findIndex(s=>s.id===e.id),n=this._messages.slice(0,t).filter(s=>s.role==="user").map(s=>s.content).pop()||"";if(n){this._state.set(h.SENDING),this._panel.setInputDisabled(!0),this._panel.showTyping(),this._emit("recommendation_started",{query:n});try{let{view:s}=await this._recommendations.getRecommendations(n),r=new E({role:"assistant",content:s.rationale||`Recommendations for: "${s.query}"`,citations:[],type:"recommendation",products:s.products,reference:s.rationale||null});this._messages.push(r),this._panel.appendMessage(r),this._emit("recommendation_done",{query:n,count:s.products.length}),this._state.set(h.READY)}catch(s){let r=new E({role:"assistant",content:this._friendlyError(s)});r.status=v.ERROR,this._messages.push(r),this._panel.appendMessage(r),this._emit("error",{error:this._friendlyError(s)}),this._state.set(h.ERROR)}finally{this._panel.hideTyping(),this._panel.setInputDisabled(!1)}}}_onStateChange(e,t){var n;(n=this._config)!=null&&n.debug&&console.info(`[ai-commerce-widget] state ${t} -> ${e}`)}_emit(e,t={}){var n;try{let s=(n=this.ownerDocument)==null?void 0:n.defaultView;if(!s||typeof s.CustomEvent!="function")return;s.dispatchEvent(new s.CustomEvent(dt,{detail:{status:e,...t}}))}catch{}}disconnectedCallback(){var e;(e=this._panel)==null||e.clearRateLimit()}api(){return{open:()=>this.open(),close:()=>this.close(),getState:()=>this.state,startNewConversation:()=>this.startNewConversation(),sendMessage:e=>this._handleSend(e)}}};function fe(){return typeof customElements!="undefined"&&!customElements.get(N)&&customElements.define(N,G),G}var ft="AI Commerce Assistant",mt="Hi, I can help you with questions about this store. What would you like to know?",Le={widgetKey:"",apiBaseUrl:""},Me="openai";function De(i,e){return i==null||i===""?e:["1","true","yes","on"].includes(String(i).toLowerCase())}function gt(i=null){let e=i||(typeof document!="undefined"?document:null);if(!e)return null;let t=null;return e.currentScript&&(t=e.currentScript),t||(t=e.querySelector("script[data-widget-key]")||e.querySelector('script[src*="widget.js"]')),t}function me(i=null){let{script:e}={script:gt(i)},t=e?e.dataset:{},n=(t.widgetKey||Le.widgetKey||"").trim(),s=(t.apiBaseUrl||Le.apiBaseUrl||"").trim(),r=(t.providerName||Me).trim(),a=(t.customerId||"").trim();if(!s){try{s=e&&e.src?new URL(e.src,window.location.href).origin:""}catch{}}if(s&&(!pe(s)||!s.startsWith("https://")&&!s.startsWith("http://")))throw new Error("ai-commerce-widget: data-api-base-url must be a valid http(s) URL.");return{script:e,widgetKey:n,apiBaseUrl:s.replace(/\/+$/,""),providerName:r||Me,title:(t.title||ft).slice(0,80),welcomeMessage:(t.welcomeMessage||mt).slice(0,500),position:t.position==="left"?"left":"right",theme:t.theme==="dark"?"dark":"light",accentColor:/^#[0-9a-fA-F]{3,8}$/.test(t.accentColor||"")?t.accentColor:null,customerId:a.length>0?a.slice(0,256):null,autoOpen:!!De(t.autoOpen,!1),debug:!!De(t.debug,!1)}}function ge(i){let e=[];return(!i.widgetKey||i.widgetKey.length<8)&&e.push("Missing or invalid widget key (data-widget-key)"),i.providerName||e.push("Missing provider name"),{valid:e.length===0,errors:e}}var Be="1.0.0",Pe=["widgetKey","apiBaseUrl","providerName","title","welcomeMessage","position","theme","accentColor","customerId","autoOpen","debug"],_=null;function be(){if(!_){let e=typeof document!="undefined"?document.querySelector(N):null;e&&(_=e)}if(!_)return!1;let i=_;return _=null,i.parentNode&&i.parentNode.removeChild(i),!0}function de(){if(typeof document=="undefined"||typeof customElements=="undefined")return null;fe();let i=document.querySelector(N);if(i)return _=i,i;let e;try{e=me()}catch(s){return typeof globalThis!="undefined"&&globalThis.AICommerceWidgetDebug===!0&&console.info("[ai-commerce-widget] invalid configuration:",s==null?void 0:s.message),null}let t=ge(e);if(!t.valid)return e.debug&&console.info("[ai-commerce-widget] configuration errors:",t.errors.join("; ")),null;let n=document.createElement(N);for(let s of Pe){let r=e[s];r!=null&&r!==""&&(n.dataset[s]=String(r))}return document.body.appendChild(n),_=n,n}function bt(){return _}function xt(){return typeof document=="undefined"?null:(document.body?de():document.addEventListener("DOMContentLoaded",()=>de(),{once:!0}),{getWidget:bt})}function Oe(i={}){var r,a,c,d,l,u,p,b,f,S,B,I,R;if(typeof document=="undefined")return null;be(),fe();let e;try{e=me()}catch{e=null}e||(e={widgetKey:"",apiBaseUrl:""});let t={widgetKey:(a=(r=i.key)!=null?r:i.widgetKey)!=null?a:e.widgetKey,apiBaseUrl:(d=(c=i.apiBase)!=null?c:i.apiBaseUrl)!=null?d:e.apiBaseUrl,customerId:(l=i.customerId)!=null?l:e.customerId,providerName:(u=i.providerName)!=null?u:e.providerName,title:(p=i.title)!=null?p:e.title,welcomeMessage:(b=i.welcomeMessage)!=null?b:e.welcomeMessage,position:(f=i.position)!=null?f:e.position,theme:(S=i.theme)!=null?S:e.theme,accentColor:(B=i.accentColor)!=null?B:e.accentColor,autoOpen:(I=i.autoOpen)!=null?I:e.autoOpen,debug:(R=i.debug)!=null?R:e.debug},n=ge({...t,customerId:t.customerId});if(!n.valid)return(t.debug||globalThis.AICommerceWidgetDebug===!0)&&console.info("[ai-commerce-widget] configuration errors:",n.errors.join("; ")),null;let s=document.createElement(N);for(let O of Pe){let $=t[O];$!=null&&$!==""&&(s.dataset[O]=String($))}return document.body.appendChild(s),_=s,s}function wt(){try{let i=globalThis.AiCommerceWidget;if(i&&i.mount)return;Object.defineProperty(globalThis,"AiCommerceWidget",{value:Object.freeze({version:Be,init:Oe,destroy:be,mount:de,getWidget:()=>_,get current(){return _}}),configurable:!1,enumerable:!1,writable:!1}),Object.defineProperty(globalThis,"AICommerceWidget",{value:Object.freeze({version:Be,init:Oe,destroy:be,mount:de,getWidget:()=>_,get current(){return _}}),configurable:!1,enumerable:!1,writable:!1})}catch{}}wt();typeof document!="undefined"&&xt();if(typeof module!="undefined"&&module.exports)module.exports={BootstrapAdapter:q,ChatAdapter:Y,ProductAdapter:U,RecommendationAdapter:Z,Message:E,Conversation:te,MessageValidator:Qe};})();
