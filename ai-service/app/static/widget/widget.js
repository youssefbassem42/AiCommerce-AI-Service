(()=>{var ue=`
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
`;var d=Object.freeze({INITIALIZING:"INITIALIZING",READY:"READY",OPENING:"OPENING",SENDING:"SENDING",RECEIVING:"RECEIVING",ERROR:"ERROR",AUTHENTICATION_FAILED:"AUTHENTICATION_FAILED",RATE_LIMITED:"RATE_LIMITED",DISABLED:"DISABLED"}),j=class{constructor(e=d.INITIALIZING){this._state=e,this._listeners=new Set}get state(){return this._state}is(...e){return e.includes(this._state)}set(e,t=null){let i=this._state;if(i!==e){this._state=e;for(let n of[...this._listeners])try{n(e,i,t)}catch{}}}subscribe(e){return this._listeners.add(e),()=>this._listeners.delete(e)}};var f=Object.freeze({HTTP:"http",NETWORK:"network",TIMEOUT:"timeout",ABORTED:"aborted",INVALID_RESPONSE:"invalid_response"}),Se=new Set([500,502,503,504]);var u=class extends Error{constructor({status:e=null,kind:t=f.HTTP,message:i="Request failed",detail:n=null,retryAfterSeconds:r=null,headers:a={},retryable:l=!1,requestId:c=null}){super(i),this.name="ApiError",this.status=e,this.kind=t,this.detail=n,this.retryAfterSeconds=r,this.headers=a,this.retryable=l,this.requestId=c}isRateLimited(){return this.status===429}isAuth(){return this.status===401}isForbidden(){return this.status===403}is5xx(){return this.status!==null&&Se.has(this.status)}isNetwork(){return this.kind===f.NETWORK||this.kind===f.TIMEOUT}rateLimitHeaders(){var e,t,i,n;return{retryAfter:Te(this.headers["retry-after"]),limit:(e=this.headers["x-ratelimit-limit"])!=null?e:null,remaining:(t=this.headers["x-ratelimit-remaining"])!=null?t:null,reset:(i=this.headers["x-ratelimit-reset"])!=null?i:null,tier:(n=this.headers["x-ratelimit-tier"])!=null?n:null}}};function Te(s){if(s==null||s==="")return null;let e=Number(s);if(Number.isFinite(e)&&e>=0)return e;let t=Date.parse(s);return Number.isFinite(t)?Math.max(0,Math.round((t-Date.now())/1e3)):null}function pe(s,e){return s.isAuth()||s.isRateLimited()||s.status===422||s.status===400||s.status===404||s.status===403?!1:s.is5xx()||s.isNetwork()?e<1:!1}function fe(s){let t=Math.random()*.3+.85;return Math.min(5e3,Math.round(500*Math.pow(2,s)*t))}var Ne=3e4,Re=1;function Le(){if(typeof crypto!="undefined"&&crypto.randomUUID)return crypto.randomUUID();let s=new Uint8Array(16);return(crypto||globalThis.crypto).getRandomValues(s),Array.from(s,e=>e.toString(16).padStart(2,"0")).join("")}var me=s=>new Promise(e=>setTimeout(e,s)),D=class{constructor({baseUrl:e,getToken:t,bootstrap:i,timeoutMs:n=Ne,backoff:r=fe}){this.baseUrl=String(e).replace(/\/+$/,""),this.getToken=t,this.bootstrap=i,this.timeoutMs=n,this.backoff=r,this._fetch=typeof fetch!="undefined"?fetch.bind(globalThis):null}async request(e){if(!this._fetch)throw new u({kind:f.NETWORK,message:"Fetch API is not available in this environment."});let{path:t,query:i,body:n,headers:r={},auth:a=!1,isBootstrap:l=!1,widgetKey:c=null,timeoutMs:p=this.timeoutMs}=e,v=this.buildUrl(t,i),h=new Headers(r);if(h.set("Accept","application/json"),h.set("X-Correlation-ID",Le()),n!=null&&h.set("Content-Type","application/json"),l){if(!c)throw new u({kind:f.INVALID_RESPONSE,message:"Widget key missing for bootstrap."});h.set("X-Widget-Key",c)}else if(a){let m=this.getToken();m&&h.set("Authorization",`Bearer ${m}`)}let w=h.get("X-Correlation-ID");for(let m=0;;m+=1){let E;try{E=await this._fetchWithTimeout(v,h,n,p)}catch(M){if(Oe(M))throw new u({kind:f.TIMEOUT,message:"Request timed out.",requestId:w});if(Be(m)){await me(this.backoff(m));continue}throw new u({kind:f.NETWORK,message:"Unable to connect to the assistant.",retryable:!0,requestId:w})}let{data:L,status:k}=await Me(E);if(k>=200&&k<300)return this.resetAuthRetry(),{data:L,status:k,headers:E.headers};let S=De(E,L,k,w);if(S.isAuth()&&a&&this.bootstrap&&!this._authRetried){this._authRetried=!0;try{await this.bootstrap({replacedToken:!0});continue}catch{throw new u({kind:f.HTTP,status:401,message:"Your AI assistant session expired. Reconnecting...",retryable:!1,requestId:w})}}if(pe(S,m)){await me(this.backoff(m));continue}throw S}}resetAuthRetry(){this._authRetried=!1}buildUrl(e,t){let i=new URL(`${this.baseUrl}${e.startsWith("/")?e:`/${e}`}`);if(t)for(let[n,r]of Object.entries(t))r!=null&&r!==""&&i.searchParams.set(n,String(r));return i}post(e,t,i={}){let{query:n,...r}=i;return this.request({path:e,query:n,body:t,...r})}get(e,t,i={}){return this.request({path:e,query:t,...i})}async _fetchWithTimeout(e,t,i,n){return this._fetchJson("POST",e,t,i,n)}async _fetchJson(e,t,i,n,r){let a=new AbortController,l=setTimeout(()=>a.abort(),r);try{return await this._fetch(t,{method:e,headers:i,body:n!=null?JSON.stringify(n):void 0,signal:a.signal,credentials:"omit",cache:"no-store"})}finally{clearTimeout(l)}}};async function Me(s){let e=await s.text(),t=s.headers.get("content-type")||"",i=null;if(e&&t.includes("application/json"))try{i=JSON.parse(e)}catch{i=null}return{data:i,status:s.status}}function De(s,e,t,i){let n={};for(let c of["retry-after","x-ratelimit-limit","x-ratelimit-remaining","x-ratelimit-reset","x-ratelimit-tier"]){let p=s.headers.get(c);p!==null&&(n[c]=p)}let r=n["retry-after"]!=null?Number(n["retry-after"]):null,a=null;e&&typeof e=="object"&&typeof e.detail=="string"&&(a=e.detail);let l=t>=500;return new u({status:t,kind:f.HTTP,message:`Request failed with status ${t}`,detail:a,retryAfterSeconds:Number.isFinite(r)?r:null,headers:n,retryable:l,requestId:i})}function Be(s){return s<Re}function Oe(s){return s&&(s.name==="AbortError"||s.name==="TimeoutError")}var T=class extends Error{constructor(e){super(e),this.name="BootstrapParseError"}},P=class{static adapt(e){if(!e||typeof e!="object"||Array.isArray(e))throw new T("Bootstrap response is not an object.");let{access_token:t,expires_in:i,widget_id:n,configuration:r}=e;if(typeof t!="string"||t.length===0)throw new T("Bootstrap response missing access_token.");let a=Number(i);if(!Number.isFinite(a)||a<=0)throw new T("Bootstrap response missing valid expires_in.");if(typeof n!="string"||n.length===0)throw new T("Bootstrap response missing widget_id.");let l=r&&typeof r=="object"?r:{};return{accessToken:t,expiresIn:Math.floor(a),widgetId:n,configuration:{chat:l.chat===!0,recommendations:l.recommendations===!0}}}};var Ue=30,G=class{constructor({widgetKey:e,apiClient:t,marginSeconds:i=Ue,now:n=()=>Math.floor(Date.now()/1e3)}){this.widgetKey=e,this.apiClient=t,this.marginSeconds=i,this._now=n,this._token=null,this._expiresAt=0,this._inFlight=null,this._bootstrapError=null,this._bootstrapDone=!1}get hasToken(){return this._token!==null}getToken(){return this._token}isTokenExpired(){return this._token?this._now()>=this._expiresAt-this.marginSeconds:!0}get expiresInSeconds(){return Math.max(0,this._expiresAt-this._now())}async bootstrap(e={}){let{force:t=!1}=e;return this._inFlight?this._inFlight:(this._bootstrapDone=!1,this._inFlight=this._runBootstrap(t).finally(()=>{this._inFlight=null,this._bootstrapDone=!0}),this._inFlight)}async _runBootstrap(e){try{let{data:t}=await this.apiClient.post("/api/v1/widget/bootstrap",void 0,{isBootstrap:!0,auth:!1,widgetKey:this.widgetKey}),i=P.adapt(t);this._token=i.accessToken;let n=this._now();return this._expiresAt=n+i.expiresIn,this._bootstrapError=null,i}catch(t){throw this._token=null,this._expiresAt=0,this._bootstrapError=t instanceof u?t:new u({kind:f.NETWORK,message:"Bootstrap failed."}),this._bootstrapError}}async ensureToken(){if(!this.isTokenExpired())return this._token;if(await this.bootstrap(),!this._token)throw new u({kind:f.INVALID_RESPONSE,message:"Bootstrap did not return an access token."});return this._token}async refresh(){return this.bootstrap({force:!0})}clearBootstrapError(){this._bootstrapError=null}get lastBootstrapError(){return this._bootstrapError}reset(){this._token=null,this._expiresAt=0,this._inFlight=null,this._bootstrapError=null}};var ze=/^(https?:|mailto:)/i;function re(s){if(typeof s!="string"||s.length===0||s.length>2048)return!1;let e=s.trim();if(!ze.test(e))return!1;try{let t=new URL(e);return["http:","https:","mailto:"].includes(t.protocol)}catch{return!1}}function H(s){return s==null?"":String(s).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/g,"")}function W(s,e){if(!re(s))return null;let t=e.createElement("a");return t.href=s,t.target="_blank",t.rel="noopener noreferrer nofollow",t}var N=class extends Error{constructor(e){super(e),this.name="ChatParseError"}};function C(s){return typeof s=="string"&&s.length>0}function Fe(s,e){let t=(i,n)=>{let r=Number(i);return Number.isFinite(r)?r:n};return{index:C(s==null?void 0:s.index)?Number(s.index):typeof(s==null?void 0:s.index)=="number"?s.index:e,documentTitle:C(s==null?void 0:s.document_title)?s.document_title:null,contentSnippet:C(s==null?void 0:s.content_snippet)?s.content_snippet:null,score:typeof s=="object"&&s!==null?t(s==null?void 0:s.score,null):null,rank:typeof s=="object"&&s!==null?t(s==null?void 0:s.rank,null):null}}var q=class{static adapt(e){if(!e||typeof e!="object"||Array.isArray(e))throw new N("Chat response is not an object.");if(!C(e.response))throw new N("Chat response missing text.");let i=(Array.isArray(e.citations)?e.citations:[]).map((n,r)=>Fe(n,r)).filter(n=>n.documentTitle!==null||n.contentSnippet!==null).slice(0,20);return{content:e.response,citations:i,conversationId:C(e.conversation_id)?e.conversation_id:null,confidenceScore:typeof e.confidence_score=="number"&&Number.isFinite(e.confidence_score)?e.confidence_score:null,metadata:{model:C(e.model)?e.model:null,provider:C(e.provider)?e.provider:null,latencyMs:typeof e.latency_ms=="number"?e.latency_ms:null,usage:e.usage&&typeof e.usage=="object"?{promptTokens:Number(e.usage.prompt_tokens)||0,completionTokens:Number(e.usage.completion_tokens)||0,totalTokens:Number(e.usage.total_tokens)||0,cost:Number(e.usage.cost)||0}:null}}}};var b=Object.freeze({PENDING:"pending",SENDING:"sending",SENT:"sent",ERROR:"error"}),je=0,_=class{constructor({role:e,content:t,citations:i=[],recommendations:n=[]}){this.id=`msg_${Date.now().toString(36)}_${je++}`,this.role=e,this.content=t,this.citations=i,this.recommendations=n,this.status=b.SENT,this.retryable=!1,this.errorText=null,this.createdAt=new Date}markSending(){this.status=b.SENDING}markSent(){this.status=b.SENT}markError(e,t=!0){this.status=b.ERROR,this.errorText=e,this.retryable=t}isPending(){return this.status===b.PENDING||this.status===b.SENDING}};var ge=4e3;function Pe(s){if(s==null)return{valid:!1,error:"Please type a message.",value:""};let e=H(s).trim();return e.length===0?{valid:!1,error:"Please type a message.",value:""}:e.length>ge?{valid:!1,error:`Message is too long (maximum ${ge} characters).`,value:e}:{valid:!0,error:null,value:e}}var K=class{constructor({apiClient:e,authManager:t,conversation:i,config:n}){this.apiClient=e,this.authManager=t,this.conversation=i,this.config=n,this._inFlight=null}get providerName(){return this.config.providerName}async sendMessage(e,t={}){let i=Pe(e);if(!i.valid)throw new Error(i.error);return this._inFlight?this._inFlight:(this._inFlight=this._send(i.value,t).finally(()=>{this._inFlight=null}),this._inFlight)}async _send(e,t){await this.authManager.ensureToken();let i={message:e,conversation_id:this.conversation.id},n=this._resolveCustomerId(t.customerId);n&&(i.customer_id=n);let{data:r}=await this.apiClient.post("/api/v1/widget/chat",i,{auth:!0,query:{provider_name:this.providerName}}),a;try{a=q.adapt(r)}catch(c){throw c instanceof N?new Error("The assistant returned an unreadable response."):c}return this.conversation.updateFromResponse(a.conversationId),{message:new _({role:"assistant",content:a.content,citations:a.citations}),confidenceScore:a.confidenceScore,conversationId:a.conversationId}}_resolveCustomerId(e){let t=e!=null?e:this.config.customerId;return typeof t=="string"&&t.trim().length>0?t.trim().slice(0,256):null}get hasInFlightRequest(){return this._inFlight!==null}};var R=class extends Error{constructor(e){super(e),this.name="RecommendationParseError"}};function y(s){return typeof s=="string"&&s.length>0?s:null}function Ge(s,e){if(!s||typeof s!="object"||Array.isArray(s))return null;let t=y(s.price),i=y(s.currency),n=Array.isArray(s.specs)?s.specs.map(a=>a&&typeof a=="object"&&!Array.isArray(a)?{name:y(a.name),value:y(a.value)}:null).filter(a=>a!==null&&(a.name!==null||a.value!==null)).slice(0,12):[],r=Array.isArray(s.match_reasons)?s.match_reasons.filter(a=>typeof a=="string"&&a.length>0).slice(0,6):[];return{id:y(s.product_id)||`product_${e}`,title:y(s.title)||null,price:t,currency:i,imageUrl:y(s.image_url),productUrl:y(s.product_url),specs:n,matchReasons:r}}var $=class{static adapt(e){if(!e||typeof e!="object"||Array.isArray(e))throw new R("Recommendation response is not an object.");if(!y(e.query))throw new R("Recommendation response missing query.");let i=(Array.isArray(e.products)?e.products:[]).map(Ge).filter(n=>n!==null);return{query:e.query,rationale:y(e.rationale),totalCount:Number.isFinite(Number(e.total_count))?Number(e.total_count):i.length,products:i}}};var be=2e3;function He(s){if(s==null)return{valid:!1,error:"Please type a message.",value:""};let e=H(s).trim();return e.length===0?{valid:!1,error:"Please type a message.",value:""}:e.length>be?{valid:!1,error:`Message is too long (maximum ${be} characters).`,value:e}:{valid:!0,error:null,value:e}}var Y=class{constructor({apiClient:e,authManager:t,config:i}){this.apiClient=e,this.authManager=t,this.config=i}async getRecommendations(e,t=null){let i=He(e);if(!i.valid)throw new Error(i.error);await this.authManager.ensureToken();let n={message:i.value},r=t!=null?String(t).trim():this.config.customerId;r&&(n.customer_id=r.slice(0,256));let{data:a}=await this.apiClient.post("/api/v1/widget/recommendations",n,{auth:!0}),l;try{l=$.adapt(a)}catch(c){throw c instanceof R?new Error("The store returned unreadable recommendations."):c}return{view:l,raw:l}}};var We="This assistant is not available for this store.",xe="Unable to initialize the store assistant.",qe="The assistant is temporarily unavailable. Please try again shortly.",we="Unable to connect to the assistant.",Ke="Too many requests. Please wait a moment and try again.",$e="Your AI assistant session expired. Reconnecting...",Ye="You've reached today's assistant message limit. Please try again later.",Ve="This store's AI assistant is temporarily unavailable.",B="Something went wrong. Please try again.";function ae(s,e={}){let{isBootstrap:t=!1}=e;if(s&&typeof s=="object"&&s.name==="ApiError"){let n=s.status,r=s.retryAfterSeconds,a=s.detail&&typeof s.detail=="string"?s.detail.toLowerCase():"";if(n===401)return{message:t?xe:$e,kind:"auth",retryable:!t,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===403)return{message:We,kind:"disabled",retryable:!1,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===404)return{message:t?xe:B,kind:"not_found",retryable:!1,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===422||n===400)return{message:B,kind:"invalid_request",retryable:!1,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===409)return{message:B,kind:"conflict",retryable:!1,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(n===429)return a.includes("quota")||a.includes("token")?{message:Ve,kind:"quota",retryable:!1,retryAfterSeconds:r,rateLimit:s.rateLimitHeaders()}:a.includes("daily")||a.includes("consumer")?{message:Ye,kind:"consumer_limit",retryable:!1,retryAfterSeconds:r,rateLimit:s.rateLimitHeaders()}:{message:Ke,kind:"rate_limited",retryable:!0,retryAfterSeconds:r,rateLimit:s.rateLimitHeaders()};if(n!==null&&n>=500)return{message:qe,kind:"server_error",retryable:!0,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(s.kind===f.TIMEOUT)return{message:we,kind:"timeout",retryable:!0,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()};if(s.kind===f.NETWORK)return{message:we,kind:"network",retryable:!0,retryAfterSeconds:null,rateLimit:s.rateLimitHeaders()}}let i=s&&typeof s=="object"&&typeof s.message=="string"&&s.message.length>0?s.message:B;return{message:i.length>500?B:i,kind:"unknown",retryable:!1,retryAfterSeconds:null,rateLimit:null}}var V=class{constructor(){this._conversationId=null,this._startedAt=Date.now()}get id(){return this._conversationId}updateFromResponse(e){typeof e=="string"&&e.length>0&&(this._conversationId=e)}reset(){this._conversationId=null,this._startedAt=Date.now()}};function o(s,e,t={},i=[]){let n=s.createElement(e);for(let[r,a]of Object.entries(t))a==null||a===!1||(r==="class"?n.className=a:r.startsWith("on")&&typeof a=="function"?n.addEventListener(r.slice(2).toLowerCase(),a):r==="dataset"?Object.assign(n.dataset,a):n.setAttribute(r,a===!0?"":String(a)));for(let r of i)r instanceof Node?n.appendChild(r):r!=null&&n.appendChild(s.createTextNode(String(r)));return n}function ye(s){for(;s.firstChild;)s.removeChild(s.firstChild)}function A(s,e){var t;for(;s.firstChild;)s.removeChild(s.firstChild);s.appendChild((t=s.ownerDocument)==null?void 0:t.createTextNode(String(e)))}function oe(s){let e=["button:not([disabled])","[href]","input:not([disabled])","textarea:not([disabled])","select:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");return[...s.querySelectorAll(e)].filter(t=>{let i=t.ownerDocument.defaultView.getComputedStyle(t);return i&&i.visibility!=="hidden"&&i.display!=="none"})}var X=class{constructor(e,t){this.shadowRoot=e,this.doc=t,this.root=o(t,"div",{class:"widget-root"}),e.appendChild(this.root),this.launcherSlot=o(t,"div",{class:"launcher-slot"}),this.panelSlot=o(t,"div",{class:"panel-slot"}),this.root.appendChild(this.launcherSlot),this.root.appendChild(this.panelSlot)}mountLauncher(e){this.launcherSlot.appendChild(e)}mountPanel(e){this.panelSlot.appendChild(e)}focusElement(e){e&&typeof e.focus=="function"&&e.focus()}};var Xe={chatBubble:{viewBox:"0 0 24 24",path:"M12 3C6.48 3 2 6.94 2 11.8c0 2.66 1.3 5.04 3.4 6.62-.2 1.42-.94 3.1-1.94 4.08-.13.13-.04.35.14.36 1.52.1 3.24-.46 4.5-1.3.9.22 1.87.34 2.9.34 5.52 0 10-3.94 10-8.8S17.52 3 12 3z"},close:{viewBox:"0 0 24 24",path:"M18.3 5.71 12 12l6.3 6.29a1 1 0 1 1-1.42 1.42L12 13.41l-6.29 6.3a1 1 0 0 1-1.42-1.42L10.59 12 4.29 5.71a1 1 0 0 1 1.42-1.42L12 10.59l6.29-6.3a1 1 0 1 1 1.42 1.42z"},sparkle:{viewBox:"0 0 24 24",path:"M12 2l1.8 5.6L19.4 9.4l-5.6 1.8L12 16.8l-1.8-5.6L4.6 9.4l5.6-1.8L12 2zM19 14l.9 2.6L22.5 17.5l-2.6.9L19 21l-.9-2.6-2.6-.9 2.6-.9L19 14zM5 15l.7 2 2 .7-2 .7L5 20.4l-.7-2-2-.7 2-.7L5 15z"},plus:{viewBox:"0 0 24 24",path:"M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5z"},send:{viewBox:"0 0 24 24",path:"M3.4 20.4 20.85 12 3.4 3.6 3.4 10l12 2-12 2 0 6.4z"},chevronLeft:{viewBox:"0 0 24 24",path:"M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z"},chevronRight:{viewBox:"0 0 24 24",path:"M8.59 16.59 10 18l6-6-6-6-1.41 1.41L13.17 12z"}};function x(s,e,t={}){let i=typeof e=="string"?Xe[e]:e,n="http://www.w3.org/2000/svg",r=s.createElementNS(n,"svg");r.setAttribute("viewBox",i.viewBox),r.setAttribute("aria-hidden","true");for(let[l,c]of Object.entries(t))c!=null&&c!==!1&&r.setAttribute(l,String(c));let a=s.createElementNS(n,"path");return a.setAttribute("d",i.path),r.appendChild(a),r}var _e={"aria-label":"Show AI assistant","aria-controls":"ac-widget-panel"},J=class{constructor(e,{onClick:t}){this.doc=e,this.onClick=t,this.button=o(e,"button",{type:"button",class:"launcher","aria-label":_e["aria-label"],"aria-expanded":"false","aria-controls":_e["aria-controls"],"aria-haspopup":"dialog",onclick:r=>{this.onClick(r)}});let i=o(e,"span",{class:"launcher-open-svg"});i.appendChild(x(e,"chatBubble",{class:"launcher-svg"}));let n=o(e,"span",{class:"launcher-close-svg"});n.appendChild(x(e,"close",{class:"launcher-svg"})),this.button.appendChild(i),this.button.appendChild(n)}setExpanded(e){this.button.setAttribute("aria-expanded",String(e))}get element(){return this.button}};var Z=class{static create(e,t){var r;let i=Array.isArray(t)?t.filter(a=>a&&typeof a=="object"):[];if(i.length===0)return null;let n=o(e,"div",{class:"citations",role:"group"});n.appendChild(o(e,"div",{class:"citations-title"},["Sources"]));for(let a of i){let l=o(e,"div",{class:"citation"}),c=o(e,"span",{class:"citation-index"});A(c,String((r=a.index)!=null?r:"\u2022")),l.appendChild(c);let p=o(e,"div",{});a.documentTitle&&p.appendChild(o(e,"div",{class:"citation-title"},[a.documentTitle])),a.contentSnippet&&p.appendChild(o(e,"div",{class:"citation-snippet"},[a.contentSnippet])),l.appendChild(p),n.appendChild(l)}return n}};var Q=class{static create(e,t){let i;if(t.productUrl&&W(t.productUrl,e)?i=W(t.productUrl,e):i=o(e,"div",{class:"recommendation-card"}),i.classList.add("recommendation-card"),t.imageUrl&&W(t.imageUrl,e)){let r=e.createElement("img");r.className="recommendation-image",r.loading="lazy",r.alt=t.title?`Image of ${t.title}`:"Product image",r.src=t.imageUrl,r.addEventListener("error",()=>r.remove()),i.appendChild(r)}else i.appendChild(o(e,"div",{class:"recommendation-image"}));let n=o(e,"div",{class:"recommendation-body"});if(t.title&&n.appendChild(o(e,"div",{class:"recommendation-title"},[t.title])),t.price){let r=o(e,"div",{class:"recommendation-price"});A(r,t.currency&&t.currency!==t.price?`${t.currency} ${t.price}`:t.price),n.appendChild(r)}if(Array.isArray(t.matchReasons)&&t.matchReasons.length>0){let r=o(e,"div",{class:"recommendation-reasons"});for(let a of t.matchReasons.slice(0,6))r.appendChild(o(e,"span",{class:"reason-badge"},[a]));n.appendChild(r)}return i.appendChild(n),i}static list(e,t,i={}){let n=Array.isArray(t)?t.filter(h=>h&&typeof h=="object"):[];if(n.length===0)return null;let r=o(e,"div",{class:"recommendations",role:"group"});r.appendChild(o(e,"div",{class:"recommendations-title"},["Recommended for you"]));let a=o(e,"div",{class:"recommendations-scroller",tabindex:"0","aria-label":"Product recommendations"});for(let h of n.slice(0,8))a.appendChild(this.create(e,h));let l=o(e,"div",{class:"recommendations-controls"}),c=h=>{let w=a.querySelector(".recommendation-card"),m=w?w.getBoundingClientRect().width+10:260;a.scrollBy({left:h*m,behavior:"smooth"})},p=o(e,"button",{type:"button",class:"carousel-arrow","aria-label":"Previous recommendations",onclick:()=>c(-1)});p.appendChild(x(e,"chevronLeft",{class:"carousel-arrow-icon"}));let v=o(e,"button",{type:"button",class:"carousel-arrow","aria-label":"Next recommendations",onclick:()=>c(1)});return v.appendChild(x(e,"chevronRight",{class:"carousel-arrow-icon"})),l.appendChild(p),l.appendChild(v),a.addEventListener("keydown",h=>{h.key==="ArrowLeft"?(h.preventDefault(),c(-1)):h.key==="ArrowRight"&&(h.preventDefault(),c(1))}),r.appendChild(a),r.appendChild(l),r}};var O=class{static create(e,t,i={}){let n=t.role==="user",r=o(e,"div",{class:`bubble-row ${n?"user":"assistant"}`,"data-message-id":t.id}),a=o(e,"div",{class:"bubble-column"}),l=o(e,"div",{class:`bubble ${n?"user":"assistant"} ${t.status===b.ERROR?"bubble-error":""}`});if(t.status===b.ERROR&&t.errorText){if(A(l,t.errorText),a.appendChild(l),t.retryable&&i.onRetry){let c=o(e,"div",{class:"retry-row"});c.appendChild(o(e,"button",{type:"button",class:"action-button",onclick:()=>i.onRetry(t)},["Retry"])),a.appendChild(c)}}else{if(A(l,t.content||""),a.appendChild(l),!n&&t.citations&&t.citations.length>0){let c=Z.create(e,t.citations);c&&a.appendChild(c)}if(!n&&t.recommendations&&t.recommendations.length>0){let c=Q.list(e,t.recommendations);c&&a.appendChild(c)}!n&&i.canShowRecommendations&&i.onShowRecommendations&&!(t.recommendations&&t.recommendations.length>0)&&a.appendChild(o(e,"button",{type:"button",class:"action-button",onclick:()=>i.onShowRecommendations(t)},["Get product recommendations"]))}return r.appendChild(a),r}};var ee=class{static create(e){let t=o(e,"span",{class:"typing","aria-label":"The assistant is typing",role:"status"});for(let i=0;i<3;i+=1)t.appendChild(o(e,"span",{class:"typing-dot"}));return o(e,"div",{class:"bubble-row assistant",role:"presentation"},[o(e,"div",{class:"bubble assistant"},[t])])}};var te=class{constructor(e){this.doc=e,this.element=o(e,"div",{class:"message-area",role:"log","aria-live":"polite","aria-label":"Chat messages"}),this._typing=null,this._callbacks={},this._stickToBottom=!0,this.element.addEventListener("scroll",()=>{let{scrollTop:t,scrollHeight:i,clientHeight:n}=this.element;this._stickToBottom=i-t-n<40})}setCallbacks(e){this._callbacks=e}clear(){ye(this.element),this._typing=null,this._stickToBottom=!0}showWelcome(e){let t=o(this.doc,"div",{class:"welcome-message"});t.textContent=e,this.element.appendChild(t)}appendMessage(e){let t=O.create(this.doc,e,this._callbacks);return this.element.appendChild(t),this._scrollToBottom(),t}replaceMessage(e){let t=this.element.querySelector(`[data-message-id="${CSS.escape(e.id)}"]`);t&&t.parentNode&&(t.parentNode.replaceChild(O.create(this.doc,e,this._callbacks),t),this._scrollToBottom())}showTyping(){this._typing||(this._typing=ee.create(this.doc),this.element.appendChild(this._typing),this._scrollToBottom())}hideTyping(){this._typing&&this._typing.parentNode&&this._typing.parentNode.removeChild(this._typing),this._typing=null}showState(e,t){let i=o(this.doc,"div",{class:"state-box",role:"status"});return e&&i.appendChild(o(this.doc,"div",{class:"state-box-title"},[e])),t&&i.appendChild(o(this.doc,"div",{class:"state-box-text"},[t])),this.element.appendChild(i),i}_scrollToBottom(){this._stickToBottom&&(this.element.scrollTop=this.element.scrollHeight)}};var se=class{constructor(e,{onSend:t}){this.doc=e,this.onSend=t,this._disabled=!1,this.bar=o(e,"div",{class:"input-bar"}),this.textarea=o(e,"textarea",{class:"input-textarea",rows:1,"aria-label":"Message the assistant",placeholder:"Ask me anything..."}),this.sendButton=o(e,"button",{type:"button",class:"send-button","aria-label":"Send message"}),this.sendButton.appendChild(x(e,"send")),this.sendButton.disabled=!0,this.textarea.addEventListener("input",()=>{this._autoResize()}),this.textarea.addEventListener("keydown",i=>{i.key==="Enter"&&!i.shiftKey&&(i.preventDefault(),this.submit())}),this.sendButton.addEventListener("click",()=>this.submit()),this.textarea.addEventListener("input",()=>{this.sendButton.disabled=this._disabled||this.textarea.value.trim().length===0}),this.bar.appendChild(this.textarea),this.bar.appendChild(this.sendButton)}get element(){return this.bar}setDisabled(e){this._disabled=e,this.textarea.disabled=e,this.sendButton.disabled=e||this.textarea.value.trim().length===0}isDisabled(){return this._disabled}submit(){if(this._disabled)return;let e=this.textarea.value.trim();e&&(this.textarea.value="",this._autoResize(),this.sendButton.disabled=!0,this.onSend(e))}focus(){this.textarea.focus()}_autoResize(){this.textarea.style.height="auto",this.textarea.style.height=`${Math.min(120,Math.max(40,this.textarea.scrollHeight))}px`}};var U=class{static create(e,{title:t,message:i,retryable:n=!1,onRetry:r}){let a=o(e,"div",{class:"state-box",role:"alert"});if(t&&a.appendChild(o(e,"div",{class:"state-box-title"},[t])),i&&a.appendChild(o(e,"div",{class:"state-box-text"},[i])),n&&r){let l=o(e,"button",{type:"button",class:"action-button",onclick:r},["Retry"]);l.style.marginTop="12px",a.appendChild(l)}return a}};var ie=class{constructor(e,t,i){this.doc=e,this.title=t.title,this.welcomeMessage=t.welcomeMessage,this.callbacks=i,this.messages=new te(e),this.messages.setCallbacks(i.messageHandlers),this.input=new se(e,{onSend:i.onSend}),this.hint=o(e,"div",{class:"input-hint",role:"status",hidden:!0}),this.element=this._build(),this._firstOpen=!0,this._open=!1}_build(){let e=o(this.doc,"div",{class:"panel",id:"ac-widget-panel"}),t=o(this.doc,"div",{class:"panel-header"}),i=o(this.doc,"div",{class:"panel-header-avatar"});i.appendChild(x(this.doc,"sparkle")),t.appendChild(i),t.appendChild(o(this.doc,"div",{class:"panel-header-title"},[this.title]));let n=o(this.doc,"div",{class:"panel-header-actions"}),r=o(this.doc,"button",{type:"button",class:"icon-button","aria-label":"Start a new conversation",onclick:()=>this.callbacks.onNewChat()});r.appendChild(x(this.doc,"plus"));let a=o(this.doc,"button",{type:"button",class:"icon-button","aria-label":"Close assistant",onclick:()=>this.callbacks.onClose()});return a.appendChild(x(this.doc,"close")),n.appendChild(r),n.appendChild(a),t.appendChild(n),e.appendChild(t),e.appendChild(this.messages.element),e.appendChild(this.hint),e.appendChild(this.input.element),e.addEventListener("keydown",l=>{l.key==="Tab"&&this._open&&l.target instanceof Node&&e.contains(l.target)&&this._trapTabFocus(l)}),e}_trapTabFocus(e){let t=oe(this.element);if(t.length===0)return;let i=t[0],n=t[t.length-1];e.shiftKey&&(e.target===i||!Je(this.element,e.target))?(e.preventDefault(),n.focus()):!e.shiftKey&&e.target===n&&(e.preventDefault(),i.focus())}open(){this._open=!0,this.element.classList.add("is-open"),this.element.setAttribute("aria-hidden","false"),this._firstOpen&&(this._firstOpen=!1,this.input.focus())}close(){this._open=!1,this.element.classList.remove("is-open"),this.element.setAttribute("aria-hidden","true")}get isOpen(){return this._open}get lastFocusable(){let e=oe(this.element);return e.length>0?e[e.length-1]:null}showWelcome(){this.messages.showWelcome(this.welcomeMessage)}showTyping(){this.messages.showTyping()}hideTyping(){this.messages.hideTyping()}appendMessage(e){return this.messages.appendMessage(e)}replaceMessage(e){this.messages.replaceMessage(e)}clearMessages(){this.messages.clear()}showError({title:e,message:t,retryable:i,onRetry:n}){this.messages.clear(),this.messages.element.appendChild(U.create(this.doc,{title:e,message:t,retryable:i,onRetry:n})),this.input.setDisabled(!0)}showStatus(e,t){this.messages.clear(),this.messages.element.appendChild(U.create(this.doc,{title:e,message:t,retryable:!1}))}async showRateLimit(e){this.input.setDisabled(!0);let t=Math.max(0,Math.floor(e||0)),i=()=>{if(t<=0){this.hint.hidden=!0,this.input.setDisabled(!1);return}this.hint.hidden=!1,this.hint.textContent=`Too many requests. Retry in ${t}s.`,t-=1,this._rateLimitTimer=setTimeout(i,1e3)};i()}clearRateLimit(){this._rateLimitTimer&&(clearTimeout(this._rateLimitTimer),this._rateLimitTimer=null),this.hint.hidden=!0}setInputDisabled(e){this.input.setDisabled(e)}};function Je(s,e){return s.contains(e)}var I="ai-commerce-widget",Ze="ai-commerce-widget",Qe=.3,et="If you need more help, contact the store for human support.";function tt(){return typeof crypto!="undefined"&&crypto.randomUUID?crypto.randomUUID():`s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,10)}`}var z=class extends HTMLElement{static get observedAttributes(){return["data-widget-key","data-api-base-url","data-provider-name","data-position","data-title","data-welcome-message","data-theme","data-accent-color","data-customer-id","data-debug"]}constructor(){super(),this.attachShadow({mode:"open"}),this._config=null,this._state=new j(d.INITIALIZING),this._conversation=new V,this._messages=[],this._sessionId=tt(),this._initialized=!1,this._bootstrapAttempted=!1,this._recommendationsEnabled=!1,this._chatEnabled=!1,this._onStateChange=this._onStateChange.bind(this)}connectedCallback(){if(this._initialized)return;this._initialized=!0;let e=document.createElement("style");e.textContent=ue,this.shadowRoot.appendChild(e),this._shell=new X(this.shadowRoot,this.ownerDocument),this._state.subscribe(this._onStateChange),this._init()}_init(){try{this._config=this._readConfig(),this._applyHostAttributes(this._config)}catch(e){this._fatalConfigError(e);return}this._state.set(d.READY),this._renderLauncher(),this._config.autoOpen&&this.open()}_readConfig(){let e=this.dataset;return{widgetKey:(e.widgetKey||"").trim(),apiBaseUrl:(e.apiBaseUrl||"").trim().replace(/\/+$/,""),providerName:(e.providerName||"openai").trim(),title:(e.title||"AI Commerce Assistant").slice(0,80),welcomeMessage:(e.welcomeMessage||"Hi, I can help you with questions about this store. What would you like to know?").slice(0,500),position:e.position==="left"?"left":"right",theme:e.theme==="dark"?"dark":"light",accentColor:/^#[0-9a-fA-F]{3,8}$/.test(e.accentColor||"")?e.accentColor:null,customerId:(e.customerId||"").trim().slice(0,256)||null,autoOpen:e.autoOpen==="true"||e.autoOpen==="1",debug:e.debug==="true"||e.debug==="1"}}_applyHostAttributes(e){if(this.setAttribute("data-position",e.position),e.accentColor&&(this.style.setProperty("--ac-widget-primary",e.accentColor),this.style.setProperty("--ac-widget-primary-hover",e.accentColor),this.style.setProperty("--ac-widget-user-bubble",e.accentColor)),e.theme==="dark"){this.setAttribute("data-theme","dark");for(let[t,i]of Object.entries({"--ac-widget-bg":"#111827","--ac-widget-text":"#f3f4f6","--ac-widget-text-secondary":"#9ca3af","--ac-widget-border":"#374151","--ac-widget-assistant-bubble":"#1f2937"}))this.style.setProperty(t,i)}}_fatalConfigError(e){this._state.set(d.AUTHENTICATION_FAILED),(this.dataset.debug==="true"||this.dataset.debug==="1")&&console.info("[ai-commerce-widget] configuration error",e==null?void 0:e.message)}_renderLauncher(){this._launcher=new J(this.ownerDocument,{onClick:()=>this.toggle()}),this._shell.mountLauncher(this._launcher.element)}_ensurePanel(){return this._panel?this._panel:(this._panel=new ie(this.ownerDocument,{title:this._config.title,welcomeMessage:this._config.welcomeMessage},{onClose:()=>this.close(),onNewChat:()=>this.startNewConversation(),onSend:e=>this._handleSend(e),messageHandlers:{onRetry:e=>this._retryMessage(e),canShowRecommendations:()=>this._recommendationsEnabled,onShowRecommendations:e=>this._showRecommendations(e)}}),this._shell.mountPanel(this._panel.element),this._panel.element.addEventListener("keydown",e=>{e.key==="Escape"&&(e.preventDefault(),this.close())}),this._panel)}_ensureApi(){return this._api?this._api:(this._auth=new G({widgetKey:this._config.widgetKey,apiClient:new D({baseUrl:this._config.apiBaseUrl})}),this._api=new D({baseUrl:this._config.apiBaseUrl,getToken:()=>this._auth.getToken(),bootstrap:()=>this._auth.refresh()}),this._chat=new K({apiClient:this._api,authManager:this._auth,conversation:this._conversation,config:{providerName:this._config.providerName,customerId:this._config.customerId}}),this._recommendations=new Y({apiClient:this._api,authManager:this._auth,config:{customerId:this._config.customerId}}),this._api)}get state(){return this._state.state}get conversationId(){return this._conversation.id}async open(){this._panel||this._ensurePanel(),this._state.set(d.OPENING),this._panel.open(),this._panel.showWelcome(),this._launcher.setExpanded(!0),this._panel.focus(),await this._bootstrapIfNeeded(),this._state.set(d.READY)}close(){this._panel&&(this._panel.close(),this._panel.clearRateLimit()),this._launcher&&(this._launcher.setExpanded(!1),this._launcher.element.focus()),this._state.set(d.READY),this._emit("closed")}toggle(){this._panel&&this._panel.isOpen?this.close():this.open()}startNewConversation(){this._conversation.reset(),this._messages=[],this._panel.clearMessages(),this._panel.showWelcome(),this._panel.setInputDisabled(!1),this._panel.clearRateLimit()}async _bootstrapIfNeeded(){if(!(this._bootstrapAttempted&&this._auth&&!this._auth.isTokenExpired())){this._api||this._ensureApi(),this._bootstrapAttempted=!0;try{let e=await this._auth.bootstrap();if(this._chatEnabled=e.configuration.chat,this._recommendationsEnabled=e.configuration.recommendations,this._emit("ready",{widgetId:e.widgetId,configuration:{chat:this._chatEnabled,recommendations:this._recommendationsEnabled}}),!this._chatEnabled&&!this._recommendationsEnabled){this._state.set(d.DISABLED),this._panel.showError({title:"Assistant unavailable",message:"This assistant is not available for this store."});return}!this._chatEnabled&&this._recommendationsEnabled&&this._panel.setInputDisabled(!0)}catch(e){this._handleBootstrapError(e)}}}_handleBootstrapError(e){let t=ae(e,{isBootstrap:!0});t.kind==="disabled"?this._state.set(d.DISABLED):this._state.set(d.AUTHENTICATION_FAILED),this._panel.showError({title:"Assistant unavailable",message:t.message,retryable:t.retryable,onRetry:t.retryable?()=>this._retryBootstrap():void 0})}_retryBootstrap(){this._auth&&this._auth.clearBootstrapError(),this._bootstrapAttempted=!1,this._panel.setInputDisabled(!0),this._panel.showStatus("Assistant","Reconnecting..."),this._bootstrapIfNeeded().finally(()=>{this._chatEnabled&&this._panel.setInputDisabled(!1)})}async _handleSend(e,t={}){var r,a;if(this._state.is(d.SENDING))return;this._panel&&this._panel.clearRateLimit();let i=t.existingMessage,n=i&&i.role==="user"?i:(()=>{let l=new _({role:"user",content:e});return l.markSending(),this._messages.push(l),this._panel.appendMessage(l),l})();n.markSending(),n.errorText=null,i&&this._panel.replaceMessage(n),this._state.set(d.SENDING),this._panel.setInputDisabled(!0),this._chat||this._ensureApi(),this._auth.hasToken||await this._bootstrapIfNeeded(),this._panel.showTyping(),this._emit("chat_started",{query:e});try{let l=await this._chat.sendMessage(e,{customerId:(r=t.customerId)!=null?r:null});n.markSent(),this._panel.replaceMessage(n);let c=l.message;if(this._messages.push(c),this._panel.appendMessage(c),l.confidenceScore!==null&&l.confidenceScore<Qe){let p=new _({role:"assistant",content:et});this._messages.push(p),this._panel.appendMessage(p)}this._emit("chat_done",{query:e,conversationId:(a=l.conversationId)!=null?a:null}),this._state.set(d.READY)}catch(l){n.markError(this._friendlyError(l),!0),this._panel.replaceMessage(n),this._emit("error",{error:this._friendlyError(l)}),this._applyMessageErrorState(l)}finally{this._panel.hideTyping(),this._panel.setInputDisabled(!1)}}_friendlyError(e){return e instanceof Error&&e.message&&!(e instanceof u)?e.message:ae(e).message}_applyMessageErrorState(e){var t;e instanceof u&&e.isRateLimited()?(this._state.set(d.RATE_LIMITED),this._panel.showRateLimit((t=e.retryAfterSeconds)!=null?t:10)):e instanceof u&&(e.status===403||e.status===404||e.status===422||e.status===400)?this._state.set(d.ERROR):e instanceof u&&e.status===401?this._state.set(d.ERROR):this._state.set(d.ERROR)}async _retryMessage(e){if(this._state.is(d.SENDING))return;let t=null;if(e.role==="user")t=e;else{let i=this._messages.findIndex(r=>r.id===e.id),n=i>0?this._messages[i-1]:null;n&&n.role==="user"&&(t=n)}!t||!t.content||await this._handleSend(t.content,{retry:!0,existingMessage:t})}async _showRecommendations(e){if(!this._recommendationsEnabled||this._state.is(d.SENDING))return;let t=this._messages.findIndex(n=>n.id===e.id),i=this._messages.slice(0,t).filter(n=>n.role==="user").map(n=>n.content).pop()||"";if(i){this._state.set(d.SENDING),this._panel.setInputDisabled(!0),this._panel.showTyping(),this._emit("recommendation_started",{query:i});try{let{view:n}=await this._recommendations.getRecommendations(i),r=new _({role:"assistant",content:`Recommendations for: "${n.query}"`,citations:[],recommendations:n.products});this._messages.push(r),this._panel.appendMessage(r),this._emit("recommendation_done",{query:i,count:n.products.length}),this._state.set(d.READY)}catch(n){let r=new _({role:"assistant",content:this._friendlyError(n)});r.status=b.ERROR,this._messages.push(r),this._panel.appendMessage(r),this._emit("error",{error:this._friendlyError(n)}),this._state.set(d.ERROR)}finally{this._panel.hideTyping(),this._panel.setInputDisabled(!1)}}}_onStateChange(e,t){var i;(i=this._config)!=null&&i.debug&&console.info(`[ai-commerce-widget] state ${t} -> ${e}`)}_emit(e,t={}){var i;try{let n=(i=this.ownerDocument)==null?void 0:i.defaultView;if(!n||typeof n.CustomEvent!="function")return;n.dispatchEvent(new n.CustomEvent(Ze,{detail:{status:e,...t}}))}catch{}}disconnectedCallback(){var e;(e=this._panel)==null||e.clearRateLimit()}api(){return{open:()=>this.open(),close:()=>this.close(),getState:()=>this.state,startNewConversation:()=>this.startNewConversation(),sendMessage:e=>this._handleSend(e)}}};function le(){return typeof customElements!="undefined"&&!customElements.get(I)&&customElements.define(I,z),z}var st="AI Commerce Assistant",it="Hi, I can help you with questions about this store. What would you like to know?",ve={widgetKey:"",apiBaseUrl:""},Ee="openai";function ke(s,e){return s==null||s===""?e:["1","true","yes","on"].includes(String(s).toLowerCase())}function nt(s=null){let e=s||(typeof document!="undefined"?document:null);if(!e)return null;let t=null;return e.currentScript&&(t=e.currentScript),t||(t=e.querySelector("script[data-widget-key]")||e.querySelector('script[src*="widget.js"]')),t}function ce(s=null){let{script:e}={script:nt(s)},t=e?e.dataset:{},i=(t.widgetKey||ve.widgetKey||"").trim(),n=(t.apiBaseUrl||ve.apiBaseUrl||"").trim(),r=(t.providerName||Ee).trim(),a=(t.customerId||"").trim();if(!re(n)||!n.startsWith("https://")&&!n.startsWith("http://"))throw new Error("ai-commerce-widget: data-api-base-url must be a valid http(s) URL.");return{script:e,widgetKey:i,apiBaseUrl:n.replace(/\/+$/,""),providerName:r||Ee,title:(t.title||st).slice(0,80),welcomeMessage:(t.welcomeMessage||it).slice(0,500),position:t.position==="left"?"left":"right",theme:t.theme==="dark"?"dark":"light",accentColor:/^#[0-9a-fA-F]{3,8}$/.test(t.accentColor||"")?t.accentColor:null,customerId:a.length>0?a.slice(0,256):null,autoOpen:!!ke(t.autoOpen,!1),debug:!!ke(t.debug,!1)}}function de(s){let e=[];return(!s.widgetKey||s.widgetKey.length<8)&&e.push("Missing or invalid widget key (data-widget-key)"),s.apiBaseUrl||e.push("Missing API base URL (data-api-base-url)"),s.providerName||e.push("Missing provider name"),{valid:e.length===0,errors:e}}var Ce="1.0.0",Ie=["widgetKey","apiBaseUrl","providerName","title","welcomeMessage","position","theme","accentColor","customerId","autoOpen","debug"],g=null;function he(){if(!g){let e=typeof document!="undefined"?document.querySelector(I):null;e&&(g=e)}if(!g)return!1;let s=g;return g=null,s.parentNode&&s.parentNode.removeChild(s),!0}function ne(){if(typeof document=="undefined"||typeof customElements=="undefined")return null;le();let s=document.querySelector(I);if(s)return g=s,s;let e;try{e=ce()}catch(n){return typeof globalThis!="undefined"&&globalThis.AICommerceWidgetDebug===!0&&console.info("[ai-commerce-widget] invalid configuration:",n==null?void 0:n.message),null}let t=de(e);if(!t.valid)return e.debug&&console.info("[ai-commerce-widget] configuration errors:",t.errors.join("; ")),null;let i=document.createElement(I);for(let n of Ie){let r=e[n];r!=null&&r!==""&&(i.dataset[n]=String(r))}return document.body.appendChild(i),g=i,i}function rt(){return g}function at(){return typeof document=="undefined"?null:(document.body?ne():document.addEventListener("DOMContentLoaded",()=>ne(),{once:!0}),{getWidget:rt})}function Ae(s={}){var r,a,l,c,p,v,h,w,m,E,L,k,S;if(typeof document=="undefined")return null;he(),le();let e;try{e=ce()}catch{e=null}e||(e={widgetKey:"",apiBaseUrl:""});let t={widgetKey:(a=(r=s.key)!=null?r:s.widgetKey)!=null?a:e.widgetKey,apiBaseUrl:(c=(l=s.apiBase)!=null?l:s.apiBaseUrl)!=null?c:e.apiBaseUrl,customerId:(p=s.customerId)!=null?p:e.customerId,providerName:(v=s.providerName)!=null?v:e.providerName,title:(h=s.title)!=null?h:e.title,welcomeMessage:(w=s.welcomeMessage)!=null?w:e.welcomeMessage,position:(m=s.position)!=null?m:e.position,theme:(E=s.theme)!=null?E:e.theme,accentColor:(L=s.accentColor)!=null?L:e.accentColor,autoOpen:(k=s.autoOpen)!=null?k:e.autoOpen,debug:(S=s.debug)!=null?S:e.debug},i=de({...t,customerId:t.customerId});if(!i.valid)return(t.debug||globalThis.AICommerceWidgetDebug===!0)&&console.info("[ai-commerce-widget] configuration errors:",i.errors.join("; ")),null;let n=document.createElement(I);for(let M of Ie){let F=t[M];F!=null&&F!==""&&(n.dataset[M]=String(F))}return document.body.appendChild(n),g=n,n}function ot(){try{let s=globalThis.AiCommerceWidget;if(s&&s.mount)return;Object.defineProperty(globalThis,"AiCommerceWidget",{value:Object.freeze({version:Ce,init:Ae,destroy:he,mount:ne,getWidget:()=>g,get current(){return g}}),configurable:!1,enumerable:!1,writable:!1}),Object.defineProperty(globalThis,"AICommerceWidget",{value:Object.freeze({version:Ce,init:Ae,destroy:he,mount:ne,getWidget:()=>g,get current(){return g}}),configurable:!1,enumerable:!1,writable:!1})}catch{}}ot();typeof document!="undefined"&&at();})();
