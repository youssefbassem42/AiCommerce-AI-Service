(()=>{var at=`
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
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 100%;
}

.recommendations-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ac-widget-text-secondary);
}

.recommendation-card {
  display: flex;
  gap: 10px;
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
  width: 56px;
  height: 56px;
  border-radius: 8px;
  object-fit: cover;
  background: var(--ac-widget-assistant-bubble);
  flex-shrink: 0;
}

.recommendation-body {
  min-width: 0;
  flex: 1;
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

.recommendation-empty {
  font-size: 12px;
  color: var(--ac-widget-text-secondary);
  background: var(--ac-widget-assistant-bubble);
  border-radius: 8px;
  padding: 8px 12px;
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
`;var d=Object.freeze({INITIALIZING:"INITIALIZING",READY:"READY",OPENING:"OPENING",SENDING:"SENDING",RECEIVING:"RECEIVING",ERROR:"ERROR",AUTHENTICATION_FAILED:"AUTHENTICATION_FAILED",RATE_LIMITED:"RATE_LIMITED",DISABLED:"DISABLED"}),D=class{constructor(t=d.INITIALIZING){this._state=t,this._listeners=new Set}get state(){return this._state}is(...t){return t.includes(this._state)}set(t,e=null){let i=this._state;if(i!==t){this._state=t;for(let n of[...this._listeners])try{n(t,i,e)}catch{}}}subscribe(t){return this._listeners.add(t),()=>this._listeners.delete(t)}};var p=Object.freeze({HTTP:"http",NETWORK:"network",TIMEOUT:"timeout",ABORTED:"aborted",INVALID_RESPONSE:"invalid_response"}),Et=new Set([500,502,503,504]);var h=class extends Error{constructor({status:t=null,kind:e=p.HTTP,message:i="Request failed",detail:n=null,retryAfterSeconds:r=null,headers:a={},retryable:l=!1,requestId:c=null}){super(i),this.name="ApiError",this.status=t,this.kind=e,this.detail=n,this.retryAfterSeconds=r,this.headers=a,this.retryable=l,this.requestId=c}isRateLimited(){return this.status===429}isAuth(){return this.status===401}isForbidden(){return this.status===403}is5xx(){return this.status!==null&&Et.has(this.status)}isNetwork(){return this.kind===p.NETWORK||this.kind===p.TIMEOUT}rateLimitHeaders(){var t,e,i,n;return{retryAfter:kt(this.headers["retry-after"]),limit:(t=this.headers["x-ratelimit-limit"])!=null?t:null,remaining:(e=this.headers["x-ratelimit-remaining"])!=null?e:null,reset:(i=this.headers["x-ratelimit-reset"])!=null?i:null,tier:(n=this.headers["x-ratelimit-tier"])!=null?n:null}}};function kt(s){if(s==null||s==="")return null;let t=Number(s);if(Number.isFinite(t)&&t>=0)return t;let e=Date.parse(s);return Number.isFinite(e)?Math.max(0,Math.round((e-Date.now())/1e3)):null}function ot(s,t){return s.isAuth()||s.isRateLimited()||s.status===422||s.status===400||s.status===404||s.status===403?!1:s.is5xx()||s.isNetwork()?t<1:!1}function lt(s){let e=Math.random()*.3+.85;return Math.min(5e3,Math.round(500*Math.pow(2,s)*e))}var At=3e4,St=1;function Ct(){if(typeof crypto!="undefined"&&crypto.randomUUID)return crypto.randomUUID();let s=new Uint8Array(16);return(crypto||globalThis.crypto).getRandomValues(s),Array.from(s,t=>t.toString(16).padStart(2,"0")).join("")}var ct=s=>new Promise(t=>setTimeout(t,s)),A=class{constructor({baseUrl:t,getToken:e,bootstrap:i,timeoutMs:n=At,backoff:r=lt}){this.baseUrl=String(t).replace(/\/+$/,""),this.getToken=e,this.bootstrap=i,this.timeoutMs=n,this.backoff=r,this._fetch=typeof fetch!="undefined"?fetch.bind(globalThis):null}async request(t){if(!this._fetch)throw new h({kind:p.NETWORK,message:"Fetch API is not available in this environment."});let{path:e,query:i,body:n,headers:r={},auth:a=!1,isBootstrap:l=!1,widgetKey:c=null,timeoutMs:g=this.timeoutMs}=t,vt=this.buildUrl(e,i),w=new Headers(r);if(w.set("Accept","application/json"),w.set("X-Correlation-ID",Ct()),n!=null&&w.set("Content-Type","application/json"),l){if(!c)throw new h({kind:p.INVALID_RESPONSE,message:"Widget key missing for bootstrap."});w.set("X-Widget-Key",c)}else if(a){let b=this.getToken();b&&w.set("Authorization",`Bearer ${b}`)}let N=w.get("X-Correlation-ID");for(let b=0;;b+=1){let L;try{L=await this._fetchWithTimeout(vt,w,n,g)}catch(rt){if(Nt(rt))throw new h({kind:p.TIMEOUT,message:"Request timed out.",requestId:N});if(Rt(b)){await ct(this.backoff(b));continue}throw new h({kind:p.NETWORK,message:"Unable to connect to the assistant.",retryable:!0,requestId:N})}let{data:nt,status:M}=await Tt(L);if(M>=200&&M<300)return{data:nt,status:M,headers:L.headers};let Q=It(L,nt,M,N);if(Q.isAuth()&&a&&this.bootstrap&&!this._authRetried){this._authRetried=!0;try{await this.bootstrap({replacedToken:!0});continue}catch{throw new h({kind:p.HTTP,status:401,message:"Your AI assistant session expired. Reconnecting...",retryable:!1,requestId:N})}}if(ot(Q,b)){await ct(this.backoff(b));continue}throw Q}}resetAuthRetry(){this._authRetried=!1}buildUrl(t,e){let i=new URL(`${this.baseUrl}${t.startsWith("/")?t:`/${t}`}`);if(e)for(let[n,r]of Object.entries(e))r!=null&&r!==""&&i.searchParams.set(n,String(r));return i}post(t,e,i={}){let{query:n,...r}=i;return this.request({path:t,query:n,body:e,...r})}get(t,e,i={}){return this.request({path:t,query:e,...i})}async _fetchWithTimeout(t,e,i,n){return this._fetchJson("POST",t,e,i,n)}async _fetchJson(t,e,i,n,r){let a=new AbortController,l=setTimeout(()=>a.abort(),r);try{return await this._fetch(e,{method:t,headers:i,body:n!=null?JSON.stringify(n):void 0,signal:a.signal,credentials:"omit",cache:"no-store"})}finally{clearTimeout(l)}}};async function Tt(s){let t=await s.text(),e=s.headers.get("content-type")||"",i=null;if(t&&e.includes("application/json"))try{i=JSON.parse(t)}catch{i=null}return{data:i,status:s.status}}function It(s,t,e,i){let n={};for(let c of["retry-after","x-ratelimit-limit","x-ratelimit-remaining","x-ratelimit-reset","x-ratelimit-tier"]){let g=s.headers.get(c);g!==null&&(n[c]=g)}let r=n["retry-after"]!=null?Number(n["retry-after"]):null,a=null;t&&typeof t=="object"&&typeof t.detail=="string"&&(a=t.detail);let l=e>=500;return new h({status:e,kind:p.HTTP,message:`Request failed with status ${e}`,detail:a,retryAfterSeconds:Number.isFinite(r)?r:null,headers:n,retryable:l,requestId:i})}function Rt(s){return s<St}function Nt(s){return s&&(s.name==="AbortError"||s.name==="TimeoutError")}var v=class extends Error{constructor(t){super(t),this.name="BootstrapParseError"}},B=class{static adapt(t){if(!t||typeof t!="object"||Array.isArray(t))throw new v("Bootstrap response is not an object.");let{access_token:e,expires_in:i,widget_id:n,configuration:r}=t;if(typeof e!="string"||e.length===0)throw new v("Bootstrap response missing access_token.");let a=Number(i);if(!Number.isFinite(a)||a<=0)throw new v("Bootstrap response missing valid expires_in.");if(typeof n!="string"||n.length===0)throw new v("Bootstrap response missing widget_id.");let l=r&&typeof r=="object"?r:{};return{accessToken:e,expiresIn:Math.floor(a),widgetId:n,configuration:{chat:l.chat===!0,recommendations:l.recommendations===!0}}}};var Lt=30,O=class{constructor({widgetKey:t,apiClient:e,marginSeconds:i=Lt,now:n=()=>Math.floor(Date.now()/1e3)}){this.widgetKey=t,this.apiClient=e,this.marginSeconds=i,this._now=n,this._token=null,this._expiresAt=0,this._inFlight=null,this._bootstrapError=null,this._bootstrapDone=!1}get hasToken(){return this._token!==null}getToken(){return this._token}isTokenExpired(){return this._token?this._now()>=this._expiresAt-this.marginSeconds:!0}get expiresInSeconds(){return Math.max(0,this._expiresAt-this._now())}async bootstrap(t={}){let{force:e=!1}=t;return this._inFlight?this._inFlight:(this._bootstrapDone=!1,this._inFlight=this._runBootstrap(e).finally(()=>{this._inFlight=null,this._bootstrapDone=!0}),this._inFlight)}async _runBootstrap(t){try{let{data:e}=await this.apiClient.post("/api/v1/widget/bootstrap",void 0,{isBootstrap:!0,auth:!1,widgetKey:this.widgetKey}),i=B.adapt(e);this._token=i.accessToken;let n=this._now();return this._expiresAt=n+i.expiresIn,this._bootstrapError=null,i}catch(e){throw this._token=null,this._expiresAt=0,this._bootstrapError=e instanceof h?e:new h({kind:p.NETWORK,message:"Bootstrap failed."}),this._bootstrapError}}async ensureToken(){if(!this.isTokenExpired())return this._token;if(await this.bootstrap(),!this._token)throw new h({kind:p.INVALID_RESPONSE,message:"Bootstrap did not return an access token."});return this._token}async refresh(){return this.bootstrap({force:!0})}clearBootstrapError(){this._bootstrapError=null}get lastBootstrapError(){return this._bootstrapError}reset(){this._token=null,this._expiresAt=0,this._inFlight=null,this._bootstrapError=null}};var Mt=/^(https?:|mailto:)/i;function tt(s){if(typeof s!="string"||s.length===0||s.length>2048)return!1;let t=s.trim();if(!Mt.test(t))return!1;try{let e=new URL(t);return["http:","https:","mailto:"].includes(e.protocol)}catch{return!1}}function U(s){return s==null?"":String(s).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/g,"")}function F(s,t){if(!tt(s))return null;let e=t.createElement("a");return e.href=s,e.target="_blank",e.rel="noopener noreferrer nofollow",e}var E=class extends Error{constructor(t){super(t),this.name="ChatParseError"}};function _(s){return typeof s=="string"&&s.length>0}function Dt(s,t){let e=(i,n)=>{let r=Number(i);return Number.isFinite(r)?r:n};return{index:_(s==null?void 0:s.index)?Number(s.index):typeof(s==null?void 0:s.index)=="number"?s.index:t,documentTitle:_(s==null?void 0:s.document_title)?s.document_title:null,contentSnippet:_(s==null?void 0:s.content_snippet)?s.content_snippet:null,score:typeof s=="object"&&s!==null?e(s==null?void 0:s.score,null):null,rank:typeof s=="object"&&s!==null?e(s==null?void 0:s.rank,null):null}}var z=class{static adapt(t){if(!t||typeof t!="object"||Array.isArray(t))throw new E("Chat response is not an object.");if(!_(t.response))throw new E("Chat response missing text.");let i=(Array.isArray(t.citations)?t.citations:[]).map((n,r)=>Dt(n,r)).filter(n=>n.documentTitle!==null||n.contentSnippet!==null).slice(0,20);return{content:t.response,citations:i,conversationId:_(t.conversation_id)?t.conversation_id:null,confidenceScore:typeof t.confidence_score=="number"&&Number.isFinite(t.confidence_score)?t.confidence_score:null,metadata:{model:_(t.model)?t.model:null,provider:_(t.provider)?t.provider:null,latencyMs:typeof t.latency_ms=="number"?t.latency_ms:null,usage:t.usage&&typeof t.usage=="object"?{promptTokens:Number(t.usage.prompt_tokens)||0,completionTokens:Number(t.usage.completion_tokens)||0,totalTokens:Number(t.usage.total_tokens)||0,cost:Number(t.usage.cost)||0}:null}}}};var u=Object.freeze({PENDING:"pending",SENDING:"sending",SENT:"sent",ERROR:"error"}),Bt=0,x=class{constructor({role:t,content:e,citations:i=[],recommendations:n=[]}){this.id=`msg_${Date.now().toString(36)}_${Bt++}`,this.role=t,this.content=e,this.citations=i,this.recommendations=n,this.status=u.SENT,this.retryable=!1,this.errorText=null,this.createdAt=new Date}markSending(){this.status=u.SENDING}markSent(){this.status=u.SENT}markError(t,e=!0){this.status=u.ERROR,this.errorText=t,this.retryable=e}isPending(){return this.status===u.PENDING||this.status===u.SENDING}};var dt=4e3;function Ot(s){if(s==null)return{valid:!1,error:"Please type a message.",value:""};let t=U(s).trim();return t.length===0?{valid:!1,error:"Please type a message.",value:""}:t.length>dt?{valid:!1,error:`Message is too long (maximum ${dt} characters).`,value:t}:{valid:!0,error:null,value:t}}var G=class{constructor({apiClient:t,authManager:e,conversation:i,config:n}){this.apiClient=t,this.authManager=e,this.conversation=i,this.config=n,this._inFlight=null}get providerName(){return this.config.providerName}async sendMessage(t,e={}){let i=Ot(t);if(!i.valid)throw new Error(i.error);return this._inFlight?this._inFlight:(this._inFlight=this._send(i.value,e).finally(()=>{this._inFlight=null}),this._inFlight)}async _send(t,e){await this.authManager.ensureToken();let i={message:t,conversation_id:this.conversation.id},n=this._resolveCustomerId(e.customerId);n&&(i.customer_id=n);let{data:r}=await this.apiClient.post("/api/v1/widget/chat",i,{auth:!0,query:{provider_name:this.providerName}}),a;try{a=z.adapt(r)}catch(c){throw c instanceof E?new Error("The assistant returned an unreadable response."):c}return this.conversation.updateFromResponse(a.conversationId),{message:new x({role:"assistant",content:a.content,citations:a.citations}),confidenceScore:a.confidenceScore,conversationId:a.conversationId}}_resolveCustomerId(t){let e=t!=null?t:this.config.customerId;return typeof e=="string"&&e.trim().length>0?e.trim().slice(0,256):null}get hasInFlightRequest(){return this._inFlight!==null}};var k=class extends Error{constructor(t){super(t),this.name="RecommendationParseError"}};function f(s){return typeof s=="string"&&s.length>0?s:null}function Ut(s,t){if(!s||typeof s!="object"||Array.isArray(s))return null;let e=f(s.price),i=f(s.currency),n=Array.isArray(s.specs)?s.specs.map(a=>a&&typeof a=="object"&&!Array.isArray(a)?{name:f(a.name),value:f(a.value)}:null).filter(a=>a!==null&&(a.name!==null||a.value!==null)).slice(0,12):[],r=Array.isArray(s.match_reasons)?s.match_reasons.filter(a=>typeof a=="string"&&a.length>0).slice(0,6):[];return{id:f(s.product_id)||`product_${t}`,title:f(s.title)||null,price:e,currency:i,imageUrl:f(s.image_url),productUrl:f(s.product_url),specs:n,matchReasons:r}}var P=class{static adapt(t){if(!t||typeof t!="object"||Array.isArray(t))throw new k("Recommendation response is not an object.");if(!f(t.query))throw new k("Recommendation response missing query.");let i=(Array.isArray(t.products)?t.products:[]).map(Ut).filter(n=>n!==null);return{query:t.query,rationale:f(t.rationale),totalCount:Number.isFinite(Number(t.total_count))?Number(t.total_count):i.length,products:i}}};var ht=2e3;function Ft(s){if(s==null)return{valid:!1,error:"Please type a message.",value:""};let t=U(s).trim();return t.length===0?{valid:!1,error:"Please type a message.",value:""}:t.length>ht?{valid:!1,error:`Message is too long (maximum ${ht} characters).`,value:t}:{valid:!0,error:null,value:t}}var j=class{constructor({apiClient:t,authManager:e,config:i}){this.apiClient=t,this.authManager=e,this.config=i}async getRecommendations(t,e=null){let i=Ft(t);if(!i.valid)throw new Error(i.error);await this.authManager.ensureToken();let n={message:i.value},r=e!=null?String(e).trim():this.config.customerId;r&&(n.customer_id=r.slice(0,256));let{data:a}=await this.apiClient.post("/api/v1/widget/recommendations",n,{auth:!0}),l;try{l=P.adapt(a)}catch(c){throw c instanceof k?new Error("The store returned unreadable recommendations."):c}return{view:l,raw:l}}};var zt="This assistant is not available for this store.",pt="Unable to initialize the store assistant.",Gt="The assistant is temporarily unavailable. Please try again shortly.",ut="Unable to connect to the assistant.",Pt="Too many requests. Please wait a moment and try again.",jt="Your AI assistant session expired. Reconnecting...",Ht="You've reached today's assistant message limit. Please try again later.",Wt="This store's AI assistant is temporarily unavailable.",S="Something went wrong. Please try again.";function et(s,t={}){let{isBootstrap:e=!1}=t;if(s&&typeof s=="object"&&s.name==="ApiError"){let n=s.status,r=s.retryAfterSeconds,a=s.detail&&typeof s.detail=="string"?s.detail.toLowerCase():"";if(n===401)return{message:e?pt:jt,kind:"auth",retryable:!e,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===403)return{message:zt,kind:"disabled",retryable:!1,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===404)return{message:e?pt:S,kind:"not_found",retryable:!1,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===422||n===400)return{message:S,kind:"invalid_request",retryable:!1,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===409)return{message:S,kind:"conflict",retryable:!1,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===429)return a.includes("quota")||a.includes("token")?{message:Wt,kind:"quota",retryable:!1,retryAfterSeconds:r,rateLimit:s.rateLimitHeaders()}:a.includes("daily")||a.includes("consumer")?{message:Ht,kind:"consumer_limit",retryable:!1,retryAfterSeconds:r,rateLimit:s.rateLimitHeaders()}:{message:Pt,kind:"rate_limited",retryable:!0,retryAfterSeconds:r,rateLimit:s.rateLimitHeaders()};if(n!==null&&n>=500)return{message:Gt,kind:"server_error",retryable:!0,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(s.kind===p.TIMEOUT)return{message:ut,kind:"timeout",retryable:!0,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(s.kind===p.NETWORK)return{message:ut,kind:"network",retryable:!0,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()}}let i=s&&typeof s=="object"&&typeof s.message=="string"&&s.message.length>0?s.message:S;return{message:i.length>500?S:i,kind:"unknown",retryable:!1,retryAfterSeconds:null,rateLimit:null}}var H=class{constructor(){this._conversationId=null,this._startedAt=Date.now()}get id(){return this._conversationId}updateFromResponse(t){typeof t=="string"&&t.length>0&&(this._conversationId=t)}reset(){this._conversationId=null,this._startedAt=Date.now()}};function o(s,t,e={},i=[]){let n=s.createElement(t);for(let[r,a]of Object.entries(e))a==null||a===!1||(r==="class"?n.className=a:r.startsWith("on")&&typeof a=="function"?n.addEventListener(r.slice(2).toLowerCase(),a):r==="dataset"?Object.assign(n.dataset,a):n.setAttribute(r,a===!0?"":String(a)));for(let r of i)r instanceof Node?n.appendChild(r):r!=null&&n.appendChild(s.createTextNode(String(r)));return n}function ft(s){for(;s.firstChild;)s.removeChild(s.firstChild)}function y(s,t){var e;for(;s.firstChild;)s.removeChild(s.firstChild);s.appendChild((e=s.ownerDocument)==null?void 0:e.createTextNode(String(t)))}function st(s){let t=["button:not([disabled])","[href]","input:not([disabled])","textarea:not([disabled])","select:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");return[...s.querySelectorAll(t)].filter(e=>{let i=e.ownerDocument.defaultView.getComputedStyle(e);return i&&i.visibility!=="hidden"&&i.display!=="none"})}var W=class{constructor(t,e){this.shadowRoot=t,this.doc=e,this.root=o(e,"div",{class:"widget-root"}),t.appendChild(this.root),this.launcherSlot=o(e,"div",{class:"launcher-slot"}),this.panelSlot=o(e,"div",{class:"panel-slot"}),this.root.appendChild(this.launcherSlot),this.root.appendChild(this.panelSlot)}mountLauncher(t){this.launcherSlot.appendChild(t)}mountPanel(t){this.panelSlot.appendChild(t)}focusElement(t){t&&typeof t.focus=="function"&&t.focus()}};var qt={chatBubble:{viewBox:"0 0 24 24",path:"M12 3C6.48 3 2 6.94 2 11.8c0 2.66 1.3 5.04 3.4 6.62-.2 1.42-.94 3.1-1.94 4.08-.13.13-.04.35.14.36 1.52.1 3.24-.46 4.5-1.3.9.22 1.87.34 2.9.34 5.52 0 10-3.94 10-8.8S17.52 3 12 3z"},close:{viewBox:"0 0 24 24",path:"M18.3 5.71 12 12l6.3 6.29a1 1 0 1 1-1.42 1.42L12 13.41l-6.29 6.3a1 1 0 0 1-1.42-1.42L10.59 12 4.29 5.71a1 1 0 0 1 1.42-1.42L12 10.59l6.29-6.3a1 1 0 1 1 1.42 1.42z"},sparkle:{viewBox:"0 0 24 24",path:"M12 2l1.8 5.6L19.4 9.4l-5.6 1.8L12 16.8l-1.8-5.6L4.6 9.4l5.6-1.8L12 2zM19 14l.9 2.6L22.5 17.5l-2.6.9L19 21l-.9-2.6-2.6-.9 2.6-.9L19 14zM5 15l.7 2 2 .7-2 .7L5 20.4l-.7-2-2-.7 2-.7L5 15z"},plus:{viewBox:"0 0 24 24",path:"M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5z"},send:{viewBox:"0 0 24 24",path:"M3.4 20.4 20.85 12 3.4 3.6 3.4 10l12 2-12 2 0 6.4z"}};function m(s,t,e={}){let i=typeof t=="string"?qt[t]:t,n="http://www.w3.org/2000/svg",r=s.createElementNS(n,"svg");r.setAttribute("viewBox",i.viewBox),r.setAttribute("aria-hidden","true");for(let[l,c]of Object.entries(e))c!=null&&c!==!1&&r.setAttribute(l,String(c));let a=s.createElementNS(n,"path");return a.setAttribute("d",i.path),r.appendChild(a),r}var mt={"aria-label":"Show AI assistant","aria-controls":"ac-widget-panel"},q=class{constructor(t,{onClick:e}){this.doc=t,this.onClick=e,this.button=o(t,"button",{type:"button",class:"launcher","aria-label":mt["aria-label"],"aria-expanded":"false","aria-controls":mt["aria-controls"],"aria-haspopup":"dialog",onclick:r=>{this.onClick(r)}});let i=o(t,"span",{class:"launcher-open-svg"});i.appendChild(m(t,"chatBubble",{class:"launcher-svg"}));let n=o(t,"span",{class:"launcher-close-svg"});n.appendChild(m(t,"close",{class:"launcher-svg"})),this.button.appendChild(i),this.button.appendChild(n)}setExpanded(t){this.button.setAttribute("aria-expanded",String(t))}get element(){return this.button}};var K=class{static create(t,e){var r;let i=Array.isArray(e)?e.filter(a=>a&&typeof a=="object"):[];if(i.length===0)return null;let n=o(t,"div",{class:"citations",role:"group"});n.appendChild(o(t,"div",{class:"citations-title"},["Sources"]));for(let a of i){let l=o(t,"div",{class:"citation"}),c=o(t,"span",{class:"citation-index"});y(c,String((r=a.index)!=null?r:"\u2022")),l.appendChild(c);let g=o(t,"div",{});a.documentTitle&&g.appendChild(o(t,"div",{class:"citation-title"},[a.documentTitle])),a.contentSnippet&&g.appendChild(o(t,"div",{class:"citation-snippet"},[a.contentSnippet])),l.appendChild(g),n.appendChild(l)}return n}};var $=class{static create(t,e){let i;if(e.productUrl&&F(e.productUrl,t)?i=F(e.productUrl,t):i=o(t,"div",{class:"recommendation-card"}),i.classList.add("recommendation-card"),e.imageUrl&&F(e.imageUrl,t)){let r=t.createElement("img");r.className="recommendation-image",r.loading="lazy",r.alt=e.title?`Image of ${e.title}`:"Product image",r.src=e.imageUrl,r.addEventListener("error",()=>r.remove()),i.appendChild(r)}else i.appendChild(o(t,"div",{class:"recommendation-image"}));let n=o(t,"div",{class:"recommendation-body"});if(e.title&&n.appendChild(o(t,"div",{class:"recommendation-title"},[e.title])),e.price){let r=o(t,"div",{class:"recommendation-price"});y(r,e.currency&&e.currency!==e.price?`${e.currency} ${e.price}`:e.price),n.appendChild(r)}if(Array.isArray(e.matchReasons)&&e.matchReasons.length>0){let r=o(t,"div",{class:"recommendation-reasons"});for(let a of e.matchReasons.slice(0,6))r.appendChild(o(t,"span",{class:"reason-badge"},[a]));n.appendChild(r)}return i.appendChild(n),i}static list(t,e,i={}){let n=Array.isArray(e)?e.filter(a=>a&&typeof a=="object"):[];if(n.length===0)return null;let r=o(t,"div",{class:"recommendations",role:"group"});r.appendChild(o(t,"div",{class:"recommendations-title"},["Recommended for you"]));for(let a of n.slice(0,8))r.appendChild(this.create(t,a));return r}};var C=class{static create(t,e,i={}){let n=e.role==="user",r=o(t,"div",{class:`bubble-row ${n?"user":"assistant"}`,"data-message-id":e.id}),a=o(t,"div",{class:"bubble-column"}),l=o(t,"div",{class:`bubble ${n?"user":"assistant"} ${e.status===u.ERROR?"bubble-error":""}`});if(e.status===u.ERROR&&e.errorText){if(y(l,e.errorText),a.appendChild(l),e.retryable&&i.onRetry){let c=o(t,"div",{class:"retry-row"});c.appendChild(o(t,"button",{type:"button",class:"action-button",onclick:()=>i.onRetry(e)},["Retry"])),a.appendChild(c)}}else{if(y(l,e.content||""),a.appendChild(l),!n&&e.citations&&e.citations.length>0){let c=K.create(t,e.citations);c&&a.appendChild(c)}if(!n&&e.recommendations&&e.recommendations.length>0){let c=$.list(t,e.recommendations);c&&a.appendChild(c)}!n&&i.canShowRecommendations&&i.onShowRecommendations&&!(e.recommendations&&e.recommendations.length>0)&&a.appendChild(o(t,"button",{type:"button",class:"action-button",onclick:()=>i.onShowRecommendations(e)},["Get product recommendations"]))}return r.appendChild(a),r}};var Y=class{static create(t){let e=o(t,"span",{class:"typing","aria-label":"The assistant is typing",role:"status"});for(let i=0;i<3;i+=1)e.appendChild(o(t,"span",{class:"typing-dot"}));return o(t,"div",{class:"bubble-row assistant",role:"presentation"},[o(t,"div",{class:"bubble assistant"},[e])])}};var V=class{constructor(t){this.doc=t,this.element=o(t,"div",{class:"message-area",role:"log","aria-live":"polite","aria-label":"Chat messages"}),this._typing=null,this._callbacks={},this._stickToBottom=!0,this.element.addEventListener("scroll",()=>{let{scrollTop:e,scrollHeight:i,clientHeight:n}=this.element;this._stickToBottom=i-e-n<40})}setCallbacks(t){this._callbacks=t}clear(){ft(this.element),this._typing=null,this._stickToBottom=!0}showWelcome(t){let e=o(this.doc,"div",{class:"welcome-message"});e.textContent=t,this.element.appendChild(e)}appendMessage(t){let e=C.create(this.doc,t,this._callbacks);return this.element.appendChild(e),this._scrollToBottom(),e}replaceMessage(t){let e=this.element.querySelector(`[data-message-id="${CSS.escape(t.id)}"]`);e&&e.parentNode&&(e.parentNode.replaceChild(C.create(this.doc,t,this._callbacks),e),this._scrollToBottom())}showTyping(){this._typing||(this._typing=Y.create(this.doc),this.element.appendChild(this._typing),this._scrollToBottom())}hideTyping(){this._typing&&this._typing.parentNode&&this._typing.parentNode.removeChild(this._typing),this._typing=null}showState(t,e){let i=o(this.doc,"div",{class:"state-box",role:"status"});return t&&i.appendChild(o(this.doc,"div",{class:"state-box-title"},[t])),e&&i.appendChild(o(this.doc,"div",{class:"state-box-text"},[e])),this.element.appendChild(i),i}_scrollToBottom(){this._stickToBottom&&(this.element.scrollTop=this.element.scrollHeight)}};var X=class{constructor(t,{onSend:e}){this.doc=t,this.onSend=e,this._disabled=!1,this.bar=o(t,"div",{class:"input-bar"}),this.textarea=o(t,"textarea",{class:"input-textarea",rows:1,"aria-label":"Message the assistant",placeholder:"Ask me anything..."}),this.sendButton=o(t,"button",{type:"button",class:"send-button","aria-label":"Send message"}),this.sendButton.appendChild(m(t,"send")),this.sendButton.disabled=!0,this.textarea.addEventListener("input",()=>{this._autoResize()}),this.textarea.addEventListener("keydown",i=>{i.key==="Enter"&&!i.shiftKey&&(i.preventDefault(),this.submit())}),this.sendButton.addEventListener("click",()=>this.submit()),this.textarea.addEventListener("input",()=>{this.sendButton.disabled=this._disabled||this.textarea.value.trim().length===0}),this.bar.appendChild(this.textarea),this.bar.appendChild(this.sendButton)}get element(){return this.bar}setDisabled(t){this._disabled=t,this.textarea.disabled=t,this.sendButton.disabled=t||this.textarea.value.trim().length===0}isDisabled(){return this._disabled}submit(){if(this._disabled)return;let t=this.textarea.value.trim();t&&(this.textarea.value="",this._autoResize(),this.sendButton.disabled=!0,this.onSend(t))}focus(){this.textarea.focus()}_autoResize(){this.textarea.style.height="auto",this.textarea.style.height=`${Math.min(120,Math.max(40,this.textarea.scrollHeight))}px`}};var T=class{static create(t,{title:e,message:i,retryable:n=!1,onRetry:r}){let a=o(t,"div",{class:"state-box",role:"alert"});if(e&&a.appendChild(o(t,"div",{class:"state-box-title"},[e])),i&&a.appendChild(o(t,"div",{class:"state-box-text"},[i])),n&&r){let l=o(t,"button",{type:"button",class:"action-button",onclick:r},["Retry"]);l.style.marginTop="12px",a.appendChild(l)}return a}};var J=class{constructor(t,e,i){this.doc=t,this.title=e.title,this.welcomeMessage=e.welcomeMessage,this.callbacks=i,this.messages=new V(t),this.messages.setCallbacks(i.messageHandlers),this.input=new X(t,{onSend:i.onSend}),this.hint=o(t,"div",{class:"input-hint",role:"status",hidden:!0}),this.element=this._build(),this._firstOpen=!0,this._open=!1}_build(){let t=o(this.doc,"div",{class:"panel",id:"ac-widget-panel"}),e=o(this.doc,"div",{class:"panel-header"}),i=o(this.doc,"div",{class:"panel-header-avatar"});i.appendChild(m(this.doc,"sparkle")),e.appendChild(i),e.appendChild(o(this.doc,"div",{class:"panel-header-title"},[this.title]));let n=o(this.doc,"div",{class:"panel-header-actions"}),r=o(this.doc,"button",{type:"button",class:"icon-button","aria-label":"Start a new conversation",onclick:()=>this.callbacks.onNewChat()});r.appendChild(m(this.doc,"plus"));let a=o(this.doc,"button",{type:"button",class:"icon-button","aria-label":"Close assistant",onclick:()=>this.callbacks.onClose()});return a.appendChild(m(this.doc,"close")),n.appendChild(r),n.appendChild(a),e.appendChild(n),t.appendChild(e),t.appendChild(this.messages.element),t.appendChild(this.hint),t.appendChild(this.input.element),t.addEventListener("keydown",l=>{l.key==="Tab"&&this._open&&l.target instanceof Node&&t.contains(l.target)&&this._trapTabFocus(l)}),t}_trapTabFocus(t){let e=st(this.element);if(e.length===0)return;let i=e[0],n=e[e.length-1];t.shiftKey&&(t.target===i||!Kt(this.element,t.target))?(t.preventDefault(),n.focus()):!t.shiftKey&&t.target===n&&(t.preventDefault(),i.focus())}open(){this._open=!0,this.element.classList.add("is-open"),this.element.setAttribute("aria-hidden","false"),this._firstOpen&&(this._firstOpen=!1,this.input.focus())}close(){this._open=!1,this.element.classList.remove("is-open"),this.element.setAttribute("aria-hidden","true")}get isOpen(){return this._open}get lastFocusable(){let t=st(this.element);return t.length>0?t[t.length-1]:null}showWelcome(){this.messages.showWelcome(this.welcomeMessage)}showTyping(){this.messages.showTyping()}hideTyping(){this.messages.hideTyping()}appendMessage(t){return this.messages.appendMessage(t)}replaceMessage(t){this.messages.replaceMessage(t)}clearMessages(){this.messages.clear()}showError({title:t,message:e,retryable:i,onRetry:n}){this.messages.clear(),this.messages.element.appendChild(T.create(this.doc,{title:t,message:e,retryable:i,onRetry:n})),this.input.setDisabled(!0)}showStatus(t,e){this.messages.clear(),this.messages.element.appendChild(T.create(this.doc,{title:t,message:e,retryable:!1}))}async showRateLimit(t){this.input.setDisabled(!0);let e=Math.max(0,Math.floor(t||0)),i=()=>{if(e<=0){this.hint.hidden=!0,this.input.setDisabled(!1);return}this.hint.hidden=!1,this.hint.textContent=`Too many requests. Retry in ${e}s.`,e-=1,this._rateLimitTimer=setTimeout(i,1e3)};i()}clearRateLimit(){this._rateLimitTimer&&(clearTimeout(this._rateLimitTimer),this._rateLimitTimer=null),this.hint.hidden=!0}setInputDisabled(t){this.input.setDisabled(t)}};function Kt(s,t){return s.contains(t)}var I="ai-commerce-widget";function $t(){return typeof crypto!="undefined"&&crypto.randomUUID?crypto.randomUUID():`s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,10)}`}var R=class extends HTMLElement{static get observedAttributes(){return["data-widget-key","data-api-base-url","data-provider-name","data-position","data-title","data-welcome-message","data-theme","data-accent-color","data-customer-id","data-debug"]}constructor(){super(),this.attachShadow({mode:"open"}),this._config=null,this._state=new D(d.INITIALIZING),this._conversation=new H,this._messages=[],this._sessionId=$t(),this._initialized=!1,this._bootstrapAttempted=!1,this._recommendationsEnabled=!1,this._chatEnabled=!1,this._onStateChange=this._onStateChange.bind(this)}connectedCallback(){if(this._initialized)return;this._initialized=!0;let t=document.createElement("style");t.textContent=at,this.shadowRoot.appendChild(t),this._shell=new W(this.shadowRoot,this.ownerDocument),this._state.subscribe(this._onStateChange),this._init()}_init(){try{this._config=this._readConfig(),this._applyHostAttributes(this._config)}catch(t){this._fatalConfigError(t);return}this._state.set(d.READY),this._renderLauncher(),this._config.autoOpen&&this.open()}_readConfig(){let t=this.dataset;return{widgetKey:(t.widgetKey||"").trim(),apiBaseUrl:(t.apiBaseUrl||"").trim().replace(/\/+$/,""),providerName:(t.providerName||"openai").trim(),title:(t.title||"AI Commerce Assistant").slice(0,80),welcomeMessage:(t.welcomeMessage||"Hi, I can help you with questions about this store. What would you like to know?").slice(0,500),position:t.position==="left"?"left":"right",theme:t.theme==="dark"?"dark":"light",accentColor:/^#[0-9a-fA-F]{3,8}$/.test(t.accentColor||"")?t.accentColor:null,customerId:(t.customerId||"").trim().slice(0,256)||null,autoOpen:t.autoOpen==="true"||t.autoOpen==="1",debug:t.debug==="true"||t.debug==="1"}}_applyHostAttributes(t){if(this.setAttribute("data-position",t.position),t.accentColor&&(this.style.setProperty("--ac-widget-primary",t.accentColor),this.style.setProperty("--ac-widget-primary-hover",t.accentColor),this.style.setProperty("--ac-widget-user-bubble",t.accentColor)),t.theme==="dark"){this.setAttribute("data-theme","dark");for(let[e,i]of Object.entries({"--ac-widget-bg":"#111827","--ac-widget-text":"#f3f4f6","--ac-widget-text-secondary":"#9ca3af","--ac-widget-border":"#374151","--ac-widget-assistant-bubble":"#1f2937"}))this.style.setProperty(e,i)}}_fatalConfigError(t){this._state.set(d.AUTHENTICATION_FAILED),(this.dataset.debug==="true"||this.dataset.debug==="1")&&console.info("[ai-commerce-widget] configuration error",t==null?void 0:t.message)}_renderLauncher(){this._launcher=new q(this.ownerDocument,{onClick:()=>this.toggle()}),this._shell.mountLauncher(this._launcher.element)}_ensurePanel(){return this._panel?this._panel:(this._panel=new J(this.ownerDocument,{title:this._config.title,welcomeMessage:this._config.welcomeMessage},{onClose:()=>this.close(),onNewChat:()=>this.startNewConversation(),onSend:t=>this._handleSend(t),messageHandlers:{onRetry:t=>this._retryMessage(t),canShowRecommendations:()=>this._recommendationsEnabled,onShowRecommendations:t=>this._showRecommendations(t)}}),this._shell.mountPanel(this._panel.element),this._panel.element.addEventListener("keydown",t=>{t.key==="Escape"&&(t.preventDefault(),this.close())}),this._panel)}_ensureApi(){return this._api?this._api:(this._auth=new O({widgetKey:this._config.widgetKey,apiClient:new A({baseUrl:this._config.apiBaseUrl})}),this._api=new A({baseUrl:this._config.apiBaseUrl,getToken:()=>this._auth.getToken(),bootstrap:()=>this._auth.refresh()}),this._chat=new G({apiClient:this._api,authManager:this._auth,conversation:this._conversation,config:{providerName:this._config.providerName,customerId:this._config.customerId}}),this._recommendations=new j({apiClient:this._api,authManager:this._auth,config:{customerId:this._config.customerId}}),this._api)}get state(){return this._state.state}get conversationId(){return this._conversation.id}async open(){this._panel||this._ensurePanel(),this._state.set(d.OPENING),this._panel.open(),this._panel.showWelcome(),this._launcher.setExpanded(!0),this._panel.focus(),await this._bootstrapIfNeeded(),this._state.set(d.READY)}close(){this._panel&&(this._panel.close(),this._panel.clearRateLimit()),this._launcher&&(this._launcher.setExpanded(!1),this._launcher.element.focus()),this._state.set(d.READY)}toggle(){this._panel&&this._panel.isOpen?this.close():this.open()}startNewConversation(){this._conversation.reset(),this._messages=[],this._panel.clearMessages(),this._panel.showWelcome(),this._panel.setInputDisabled(!1),this._panel.clearRateLimit()}async _bootstrapIfNeeded(){if(!(this._bootstrapAttempted&&this._auth&&!this._auth.isTokenExpired())){this._api||this._ensureApi(),this._bootstrapAttempted=!0;try{let t=await this._auth.bootstrap();if(this._chatEnabled=t.configuration.chat,this._recommendationsEnabled=t.configuration.recommendations,!this._chatEnabled&&!this._recommendationsEnabled){this._state.set(d.DISABLED),this._panel.showError({title:"Assistant unavailable",message:"This assistant is not available for this store."});return}!this._chatEnabled&&this._recommendationsEnabled&&this._panel.setInputDisabled(!0)}catch(t){this._handleBootstrapError(t)}}}_handleBootstrapError(t){let e=et(t,{isBootstrap:!0});e.kind==="disabled"?this._state.set(d.DISABLED):this._state.set(d.AUTHENTICATION_FAILED),this._panel.showError({title:"Assistant unavailable",message:e.message,retryable:e.retryable,onRetry:e.retryable?()=>this._retryBootstrap():void 0})}_retryBootstrap(){this._auth&&this._auth.clearBootstrapError(),this._bootstrapAttempted=!1,this._panel.setInputDisabled(!0),this._panel.showStatus("Assistant","Reconnecting..."),this._bootstrapIfNeeded().finally(()=>{this._chatEnabled&&this._panel.setInputDisabled(!1)})}async _handleSend(t,e={}){var r;if(this._state.is(d.SENDING))return;this._panel&&this._panel.clearRateLimit();let i=e.existingMessage,n=i&&i.role==="user"?i:(()=>{let a=new x({role:"user",content:t});return a.markSending(),this._messages.push(a),this._panel.appendMessage(a),a})();n.markSending(),n.errorText=null,i&&this._panel.replaceMessage(n),this._state.set(d.SENDING),this._panel.setInputDisabled(!0),this._chat||this._ensureApi(),this._auth.hasToken||await this._bootstrapIfNeeded(),this._panel.showTyping();try{let a=await this._chat.sendMessage(t,{customerId:(r=e.customerId)!=null?r:null});n.markSent(),this._panel.replaceMessage(n);let l=a.message;this._messages.push(l),this._panel.appendMessage(l),this._state.set(d.READY)}catch(a){n.markError(this._friendlyError(a),!0),this._panel.replaceMessage(n),this._applyMessageErrorState(a)}finally{this._panel.hideTyping(),this._panel.setInputDisabled(!1)}}_friendlyError(t){return t instanceof Error&&t.message&&!(t instanceof h)?t.message:et(t).message}_applyMessageErrorState(t){var e;t instanceof h&&t.isRateLimited()?(this._state.set(d.RATE_LIMITED),this._panel.showRateLimit((e=t.retryAfterSeconds)!=null?e:10)):t instanceof h&&(t.status===403||t.status===404||t.status===422||t.status===400)?this._state.set(d.ERROR):t instanceof h&&t.status===401?this._state.set(d.ERROR):this._state.set(d.ERROR)}async _retryMessage(t){if(this._state.is(d.SENDING))return;let e=null;if(t.role==="user")e=t;else{let i=this._messages.findIndex(r=>r.id===t.id),n=i>0?this._messages[i-1]:null;n&&n.role==="user"&&(e=n)}!e||!e.content||await this._handleSend(e.content,{retry:!0,existingMessage:e})}async _showRecommendations(t){if(!this._recommendationsEnabled||this._state.is(d.SENDING))return;let e=this._messages.findIndex(n=>n.id===t.id),i=this._messages.slice(0,e).filter(n=>n.role==="user").map(n=>n.content).pop()||"";if(i){this._state.set(d.SENDING),this._panel.setInputDisabled(!0),this._panel.showTyping();try{let{view:n}=await this._recommendations.getRecommendations(i),r=new x({role:"assistant",content:n.rationale?`Recommendations for: "${n.query}"`:`Recommendations for: "${n.query}"`,citations:[],recommendations:n.products});this._messages.push(r),this._panel.appendMessage(r),this._state.set(d.READY)}catch(n){let r=new x({role:"assistant",content:this._friendlyError(n)});r.status=u.ERROR,this._messages.push(r),this._panel.appendMessage(r),this._state.set(d.ERROR)}finally{this._panel.hideTyping(),this._panel.setInputDisabled(!1)}}}_onStateChange(t,e){var i;(i=this._config)!=null&&i.debug&&console.info(`[ai-commerce-widget] state ${e} -> ${t}`)}api(){return{open:()=>this.open(),close:()=>this.close(),getState:()=>this.state,startNewConversation:()=>this.startNewConversation(),sendMessage:t=>this._handleSend(t)}}};function gt(){return typeof customElements!="undefined"&&!customElements.get(I)&&customElements.define(I,R),R}var Yt="AI Commerce Assistant",Vt="Hi, I can help you with questions about this store. What would you like to know?",bt={widgetKey:"",apiBaseUrl:""},xt="openai";function wt(s,t){return s==null||s===""?t:["1","true","yes","on"].includes(String(s).toLowerCase())}function Xt(s=null){let t=s||(typeof document!="undefined"?document:null);if(!t)return null;let e=null;return t.currentScript&&(e=t.currentScript),e||(e=t.querySelector("script[data-widget-key]")||t.querySelector('script[src*="widget.js"]')),e}function _t(s=null){let{script:t}={script:Xt(s)},e=t?t.dataset:{},i=(e.widgetKey||bt.widgetKey||"").trim(),n=(e.apiBaseUrl||bt.apiBaseUrl||"").trim(),r=(e.providerName||xt).trim(),a=(e.customerId||"").trim();if(!tt(n)||!n.startsWith("https://")&&!n.startsWith("http://"))throw new Error("ai-commerce-widget: data-api-base-url must be a valid http(s) URL.");return{script:t,widgetKey:i,apiBaseUrl:n.replace(/\/+$/,""),providerName:r||xt,title:(e.title||Yt).slice(0,80),welcomeMessage:(e.welcomeMessage||Vt).slice(0,500),position:e.position==="left"?"left":"right",theme:e.theme==="dark"?"dark":"light",accentColor:/^#[0-9a-fA-F]{3,8}$/.test(e.accentColor||"")?e.accentColor:null,customerId:a.length>0?a.slice(0,256):null,autoOpen:!!wt(e.autoOpen,!1),debug:!!wt(e.debug,!1)}}function yt(s){let t=[];return(!s.widgetKey||s.widgetKey.length<8)&&t.push("Missing or invalid widget key (data-widget-key)"),s.apiBaseUrl||t.push("Missing API base URL (data-api-base-url)"),s.providerName||t.push("Missing provider name"),{valid:t.length===0,errors:t}}var Jt="1.0.0",Zt=["widgetKey","apiBaseUrl","providerName","title","welcomeMessage","position","theme","accentColor","customerId","autoOpen","debug"],Z=null;function it(){if(typeof document=="undefined"||typeof customElements=="undefined")return null;gt();let s=document.querySelector(I);if(s)return Z=s,s;let t;try{t=_t()}catch(n){return typeof globalThis!="undefined"&&globalThis.AICommerceWidgetDebug===!0&&console.info("[ai-commerce-widget] invalid configuration:",n==null?void 0:n.message),null}let e=yt(t);if(!e.valid)return t.debug&&console.info("[ai-commerce-widget] configuration errors:",e.errors.join("; ")),null;let i=document.createElement(I);for(let n of Zt){let r=t[n];r!=null&&r!==""&&(i.dataset[n]=String(r))}return document.body.appendChild(i),Z=i,i}function Qt(){return Z}function te(){return typeof document=="undefined"?null:(document.body?it():document.addEventListener("DOMContentLoaded",()=>it(),{once:!0}),{getWidget:Qt})}function ee(){try{let s=globalThis.AICommerceWidget;if(s&&s.mount)return;Object.defineProperty(globalThis,"AICommerceWidget",{value:Object.freeze({version:Jt,mount:it,getWidget:()=>Z}),configurable:!1,enumerable:!1,writable:!1})}catch{}}ee();typeof document!="undefined"&&te();})();
