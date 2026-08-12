# AI Commerce FastAPI — AI Token Quota, Consumer Limits, Provider Failover & Usage Reporting

## ROLE

You are acting as a:

- Staff Software Architect
- Senior FastAPI Engineer
- AI Infrastructure Engineer
- Distributed Systems Engineer
- Redis Engineer
- MongoDB Engineer
- LLM Provider Integration Engineer
- Security Engineer
- QA Engineer

You are modifying the existing AI Commerce FastAPI AI Service.

The existing service already contains:

```text
TenantContext
Widget authentication
Store isolation
RAG
AI chat
Recommendations
Provider abstraction
Model registry
Redis
MongoDB
AI runtime logging/metrics
Widget server-side AI policy
```

The current architecture has `store_id` as the canonical tenant boundary.

The current AI runtime model already records provider/model/token usage concepts such as:

```text
provider
model
promptTokens
completionTokens
latency
cost
```



---

# 1. ABSOLUTE SCOPE RULE

Do NOT redesign the existing AI architecture.

Do NOT redesign:

- TenantContext
- widget authentication
- widget bootstrap
- RAG
- recommendations
- AI providers
- model registry
- existing rate limiter
- existing conversations
- existing MongoDB collections unnecessarily
- existing OpenAPI contracts unnecessarily
- existing provider adapters

Do NOT create a second plan-management system.

Do NOT create Super Admin plan-management endpoints.

Do NOT make FastAPI the subscription authority.

.NET is the SaaS subscription/plan authority.

FastAPI is the AI execution/enforcement authority.

If you discover an unrelated improvement:

```text
DO NOT IMPLEMENT IT.
```

Record it only under:

```text
OUT OF SCOPE / FUTURE WORK
```

---

# 2. PRIMARY OBJECTIVE

Implement runtime enforcement of:

1. Store AI token quota.
2. Consumer daily message quota.
3. Plan provider/model policy.
4. Provider automatic selection.
5. Provider failover.
6. Token usage calculation.
7. Atomic token reservation.
8. Atomic consumer message reservation.
9. Usage reporting.
10. Provider-level usage reporting.
11. Session-based consumer enforcement.

---

# 3. AUTHORITATIVE PLAN CONTEXT

The input plan type comes from the .NET service.

The AI service MUST NOT trust:

```text
plan
```

from the browser/widget.

The trusted flow is:

```text
ASP.NET Core
      ↓
Authenticated trusted service context
      ↓
FastAPI
      ↓
TenantContext
      ↓
Plan Policy
```

The context must contain or allow resolution of:

```text
store_id
organization_id
plan
subscription status
billing period
renewal date
allowed providers
allowed models
token limit
consumer daily maximum
```

Use the existing internal authentication/context architecture.

Do not create a second tenant system.

---

# 4. PLAN POLICY

The runtime policy must represent:

```text
Plan
├── monthly/billing-period token limit
├── consumer daily message maximum
├── allowed providers
└── allowed models
```

The plan is configured centrally by .NET/Super Admin.

FastAPI uses the resulting policy.

Do NOT create duplicate commercial plan management endpoints.

---

# 5. BILLING PERIOD

Token usage MUST be scoped to the subscription billing period.

DO NOT use calendar month unless it exactly matches the subscription period.

The authoritative period is derived from:

```text
billing_cycle
renewal_date
Stripe subscription period
```

Conceptually:

```text
usage:{store_id}:{subscription_period_id}
```

or an equivalent key using the actual billing-period boundaries.

Do not invent a new billing-period identity if .NET already supplies one.

---

# 6. STORE TOKEN QUOTA

For every store:

```text
billing period
+
token limit
+
tokens used
+
tokens reserved
```

Example:

```text
Starter

Limit:
1,000,000

Used:
734,215

Reserved:
5,000

Available:
260,785
```

The effective available amount must account for reservations.

---

# 7. PRE-FLIGHT QUOTA CHECK IS REQUIRED

DO NOT execute an LLM request first and calculate usage afterward.

Correct:

```text
AI Request
   ↓
Resolve store
   ↓
Resolve plan
   ↓
Resolve billing period
   ↓
Determine request token budget
   ↓
Pre-flight quota check
   ↓
Atomic reservation
   ↓
Provider/model selection
   ↓
LLM request
   ↓
Actual usage
   ↓
Commit actual usage
   ↓
Release unused reservation
```

---

# 8. RESERVATION CONCEPT

Every AI request must reserve a maximum token budget before the LLM call.

Example:

```text
Limit = 1,000,000
Used = 900,000
Reserved = 50,000

Available:
50,000
```

Incoming request requires:

```text
30,000
```

Reservation succeeds:

```text
Used = 900,000
Reserved = 80,000
Remaining available = 20,000
```

Then actual LLM usage:

```text
17,000
```

Commit:

```text
Used = 917,000
Reserved = 63,000
```

The unused reservation:

```text
13,000
```

is released.

---

# 9. ATOMIC RESERVATION

Reservation MUST be atomic.

Do NOT implement:

```python
used = get()
if used + requested <= limit:
    set(used + requested)
```

because concurrent requests can violate the quota.

Use Redis atomic operations / Lua script / equivalent atomic mechanism.

Conceptually:

```text
Redis
  ↓
Atomic:
if used + reserved + requested <= limit
    reserve
else
    reject
```

No race condition may allow the store to exceed its quota.

---

# 10. STORE QUOTA KEY

Use an isolated key such as:

```text
ai:quota:{store_id}:{billing_period}
```

or equivalent according to the existing Redis conventions.

The key MUST include:

```text
store_id
billing period
```

Do not use only:

```text
plan
```

because multiple stores can share the same plan.

---

# 11. TENANT ISOLATION

Store A:

```text
store-A
```

must never consume:

```text
store-B
```

quota.

Test:

```text
Store A → 900k
Store B → 100k
```

and verify their counters remain independent.

Tenant identity MUST come from the existing authoritative tenant context.

---

# 12. ACTUAL TOKEN CALCULATION

After the provider responds, use the provider's actual usage metadata whenever available.

Calculate:

```text
total_tokens =
prompt_tokens
+
completion_tokens
```

Do NOT calculate based only on:

```text
message length
characters
approximation
```

when actual provider usage is available.

---

# 13. PROVIDER USAGE NORMALIZATION

Different providers may return usage fields differently.

Normalize them into:

```text
prompt_tokens
completion_tokens
total_tokens
```

Use an existing provider usage abstraction if one exists.

Do NOT duplicate token parsing separately in every AI route.

---

# 14. TOKEN USAGE MUST BE RECORDED

For each successful AI execution record:

```text
store_id
organization_id
billing_period
provider
model
prompt_tokens
completion_tokens
total_tokens
```

and existing fields already supported by the runtime logging architecture.

Do not remove existing fields.

The existing `ai_runtime_logs` concept already includes provider/model/token data.

---

# 15. RESERVATION FINALIZATION

After successful LLM execution:

```text
reserved_budget
        ↓
actual_tokens
```

Commit:

```text
actual_tokens
```

Release:

```text
reserved_budget - actual_tokens
```

Both operations must be safe under concurrency.

---

# 16. PROVIDER FAILURE

If the selected provider fails because of:

```text
provider unavailable
network/service unavailable
provider rate limit
provider API quota exhausted
provider credential failure
```

the AI service should select another provider that is allowed by the plan.

Do NOT expose provider selection to the consumer.

---

# 17. PROVIDER FAILOVER

Example:

```text
Starter allowed:

OpenAI
Gemini
```

Runtime:

```text
Select OpenAI
      ↓
OpenAI unavailable
      ↓
Select Gemini
      ↓
Execute
```

If Gemini also fails:

```text
No available allowed provider
      ↓
Return controlled AI availability error
```

Do NOT use a provider that the plan does not allow.

---

# 18. PROVIDER API QUOTA EXHAUSTION

If OpenAI reports its API quota is exhausted:

```text
OpenAI
   ↓
Quota exhausted
   ↓
Mark unavailable for this execution
   ↓
Select another plan-allowed provider
```

Do not permanently disable the provider unless an existing provider-health mechanism already exists.

This is request-level failover unless an existing health system says otherwise.

---

# 19. PROVIDER SELECTION

The consumer cannot choose:

```text
provider
model
```

The AI service automatically selects them.

The selection should consider:

```text
plan allowed providers
plan allowed models
current provider availability
provider failure
provider quota availability
existing model registry
existing AI execution policy
```

Do not create a competing model-selection system.

The existing server-side widget policy was specifically introduced to prevent clients from controlling AI execution parameters.

Extend that policy rather than replacing it.

---

# 20. LATEST USAGE PROVIDER POLICY

The provider/model selection must be automatic.

Do NOT expose:

```text
provider selector
model selector
```

to e-commerce consumers.

The system chooses the provider/model according to the current server-side plan policy and runtime availability.

The consumer simply sends:

```text
message
session_id
conversation context
```

as permitted by the existing API.

---

# 21. PROVIDER USAGE BREAKDOWN

Usage reporting MUST support:

```text
total usage
+
provider breakdown
+
model breakdown
```

Example:

```json
{
  "total_tokens": 734215,
  "providers": {
    "openai": {
      "tokens": 500000,
      "requests": 1200
    },
    "gemini": {
      "tokens": 234215,
      "requests": 800
    }
  }
}
```

Do not assume this exact response schema if the existing API has an established format.

Extend existing conventions.

---

# 22. USAGE REPORTING API

Create/extend the existing usage/reporting API rather than creating duplicate analytics architecture.

The merchant dashboard needs:

```text
plan
billing period
token limit
tokens used
tokens remaining
usage percentage
request count
provider breakdown
model breakdown
```

Conceptual response:

```json
{
  "plan": "starter",
  "billing_period": {
    "starts_at": "...",
    "ends_at": "..."
  },
  "tokens": {
    "limit": 1000000,
    "used": 734215,
    "reserved": 5000,
    "remaining": 260785,
    "percentage": 73.4215
  },
  "providers": {
    "openai": {
      "tokens": 500000,
      "requests": 1200
    },
    "gemini": {
      "tokens": 234215,
      "requests": 800
    }
  }
}
```

Use the actual existing API naming conventions.

---

# 23. USAGE PROGRESS BAR

The API must provide enough information for the dashboard to display:

```text
AI Usage

734,215 / 1,000,000 tokens

███████████████░░░░░

73.42%

265,785 remaining
```

The backend should return numeric values.

The frontend should calculate/render the progress bar.

---

# 24. CONSUMER DAILY MESSAGE LIMIT

The store owner controls the actual limit.

The plan provides the hard maximum.

Example:

```text
Plan maximum = 15

Store owner:
10
```

Effective:

```text
10 messages/day
```

Store owner:

```text
20
```

must be rejected because:

```text
20 > 15
```

---

# 25. SESSION-BASED CONSUMER ENFORCEMENT

The quota must use:

```text
store_id
+
session_id
+
day
```

as the consumer counter identity.

Example:

```text
ai:consumer:{store_id}:{session_id}:{date}
```

This ensures anonymous consumers are counted.

Do NOT require:

```text
customer_id
```

---

# 26. SESSION ID SECURITY

Do not trust a session ID to cross tenant boundaries.

The session must be associated with the current widget/store context.

A session belonging to:

```text
Store A
```

cannot be reused to consume:

```text
Store B
```

quota.

Validate the relationship through the existing widget/session architecture.

---

# 27. ATOMIC CONSUMER RESERVATION

Consumer messages must be concurrency-safe.

Example:

```text
limit = 15
used = 14
```

Two simultaneous requests arrive.

Only ONE may reserve message 15.

The second request must receive:

```text
DAILY_LIMIT_EXCEEDED
```

Use Redis atomic increment/check or Lua.

Do NOT use non-atomic:

```text
GET
if < limit
SET
```

---

# 28. CONSUMER LIMIT RESPONSE

When the consumer reaches the daily limit, return a dedicated controlled response.

Conceptually:

```json
{
  "error": "CONSUMER_DAILY_LIMIT_EXCEEDED",
  "message": "You have reached today's AI message limit.",
  "limit": 15,
  "used": 15,
  "reset_at": "..."
}
```

The widget can display:

> You've reached today's message limit. Please try again tomorrow.

Do not expose internal quota implementation.

---

# 29. STORE QUOTA EXCEEDED RESPONSE

When store AI token quota is exhausted:

```json
{
  "error": "STORE_TOKEN_QUOTA_EXCEEDED",
  "message": "This store has reached its AI usage limit for the current billing period.",
  "limit": 1000000,
  "used": 1000000,
  "reset_at": "..."
}
```

The widget/consumer should receive a safe consumer-facing message.

The store owner dashboard should receive enough data to explain:

```text
AI usage limit reached.
```

---

# 30. IMPORTANT — DIFFERENTIATE LIMIT TYPES

There are three independent controls:

```text
1. Store token quota
   store + billing period

2. Consumer message quota
   store + session + day

3. Plan provider/model policy
   plan
```

Do NOT combine them into one rate limiter.

---

# 31. EXISTING RATE LIMITER MUST REMAIN

The current system already has endpoint-aware rate limiting using Redis with bounded-memory fallback.

Do NOT replace it.

The new quota system is different:

```text
Rate Limiting
    ↓
requests/time

Usage Quota
    ↓
tokens/billing-period

Consumer Quota
    ↓
messages/session/day
```

All three may coexist.

---

# 32. PLAN UPGRADE

If .NET sends:

```text
Starter
1M
Used = 800k
```

then changes to:

```text
Pro
5M
```

FastAPI MUST NOT reset:

```text
800k
```

unless the subscription billing period itself changes according to the .NET/Stripe contract.

The quota entitlement changes according to the trusted plan context.

---

# 33. PLAN DOWNGRADE

The .NET service will not downgrade the active subscription before renewal.

Therefore FastAPI must honor the active plan until the new billing period begins.

At renewal:

```text
old period ends
       ↓
new plan becomes active
       ↓
new quota entitlement
       ↓
new billing period
       ↓
new usage period
```

Do not invent an independent downgrade mechanism in FastAPI.

---

# 34. REDIS USAGE

Redis should be used for the high-frequency atomic enforcement path.

At minimum:

```text
Store token reservation
Consumer daily message reservation
```

Do NOT depend on MongoDB read-modify-write for these hot-path atomic counters.

---

# 35. REDIS FAILURE

Inspect the existing Redis failure strategy.

Do not invent a new fallback that could allow quota bypass.

The current system already has Redis-first rate limiting with bounded-memory fallback.

For commercial quota enforcement, determine whether a safe bounded fallback is possible without violating quotas.

If no safe fallback exists:

```text
fail closed
```

rather than:

```text
allow unlimited AI usage
```

Do NOT silently bypass commercial quotas because Redis is unavailable.

If this conflicts with existing architecture, STOP and report the conflict before implementing.

---

# 36. USAGE PERSISTENCE

Use the existing AI runtime logging infrastructure.

The current runtime schema already contains:

```text
provider
model
promptTokens
completionTokens
cost
latency
```



Do NOT create duplicate usage records if an equivalent runtime record already exists.

If an aggregate is genuinely required for efficient dashboard reporting:

```text
store
billing period
provider
model
tokens
requests
```

introduce the minimum required structure only after checking existing repositories/collections.

---

# 37. REPORTING MUST BE TENANT ISOLATED

Store A can see:

```text
Store A usage
```

but never:

```text
Store B usage
```

Provider breakdown must also be store scoped.

Example:

```text
Store A:
OpenAI = 500k
Gemini = 200k
```

must never aggregate another store's usage.

---

# 38. PROVIDER BREAKDOWN

Usage reporting must support:

```text
Provider
Requests
Prompt tokens
Completion tokens
Total tokens
```

Example:

```text
OpenAI
requests: 1,200
prompt: 350,000
completion: 150,000
total: 500,000

Gemini
requests: 800
prompt: 150,000
completion: 84,215
total: 234,215
```

---

# 39. MODEL BREAKDOWN

Also support:

```text
model
requests
tokens
```

This is needed because a provider may expose multiple allowed models.

---

# 40. USAGE CALCULATION MUST BE CENTRALIZED

Do NOT calculate tokens independently inside:

```text
RAG
Chat
Recommendations
Agents
Streaming
```

Create/reuse one centralized usage normalization/calculation mechanism.

Conceptually:

```text
LLM Response
      ↓
UsageNormalizer
      ↓
prompt_tokens
completion_tokens
total_tokens
      ↓
QuotaCommit
      ↓
RuntimeLog
```

Do not create five independent token calculators.

---

# 41. PROVIDER FAILOVER + RESERVATION

The sequence must be carefully designed.

Preferred flow:

```text
Request
 ↓
Check store quota
 ↓
Reserve estimated/max budget
 ↓
Select provider/model
 ↓
Provider fails
 ↓
Release/adjust reservation appropriately
 ↓
Select next allowed provider
 ↓
Execute
 ↓
Actual usage
 ↓
Commit actual usage
 ↓
Release unused reservation
```

Do not double-count tokens during failover.

---

# 42. FAILED PROVIDER TOKEN USAGE

If a provider fails before consuming billable tokens:

```text
no actual usage
```

Release the reservation.

If the provider returns actual token usage before a failure:

```text
record actual usage
```

according to the provider response.

Do not blindly charge the maximum reservation.

---

# 43. PROVIDER FAILOVER MUST NOT BYPASS PLAN

If plan allows:

```text
OpenAI
Gemini
```

and both fail:

```text
DO NOT fallback to Anthropic
```

if Anthropic is not allowed.

The plan is the hard provider boundary.

---

# 44. MODEL SELECTION

The existing server-side AI execution policy must remain the enforcement point.

The effective model must be:

```text
Plan allowed models
+
Existing ModelRegistry
+
Existing provider availability
+
Server-side policy
```

Client-supplied model must never override this.

---

# 45. NO CONSUMER PROVIDER SELECTION

The widget must not expose a provider-selection UI.

The e-commerce customer only sends the message.

The AI service decides:

```text
provider
model
```

automatically.

---

# 46. REQUIRED USAGE API

Expose/extend the appropriate existing authenticated dashboard endpoint.

It must return:

```text
current plan
billing period
token limit
tokens used
tokens reserved
tokens remaining
percentage
reset/renewal timestamp
provider breakdown
model breakdown
```

Do not create a second analytics API if an existing usage/analytics endpoint can be extended.

---

# 47. REQUIRED TEST MATRIX

## Store quota

```text
Q01 — Store starts with zero usage
Q02 — Reservation succeeds under limit
Q03 — Reservation fails at limit
Q04 — Reservation fails above limit
Q05 — Actual usage commits correctly
Q06 — Unused reservation released
Q07 — Concurrent reservations cannot exceed limit
Q08 — Store A cannot consume Store B quota
```

## Consumer quota

```text
C01 — Session starts at zero
C02 — Message reservation succeeds under limit
C03 — Message 15 succeeds when limit=15
C04 — Message 16 rejected
C05 — Concurrent requests cannot create message 16+
C06 — Session A cannot consume Session B
C07 — Store A session cannot consume Store B quota
C08 — Anonymous session is counted
```

## Token calculation

```text
T01 — prompt + completion = total
T02 — provider usage normalized correctly
T03 — provider-specific usage format supported
T04 — missing usage handled according to existing provider behavior
T05 — actual usage replaces/reconciles reservation
```

## Provider selection

```text
P01 — Only plan-allowed providers selected
P02 — Only plan-allowed models selected
P03 — Consumer cannot force provider
P04 — Consumer cannot force model
P05 — Provider failure triggers fallback
P06 — Provider API quota exhaustion triggers fallback
P07 — Disallowed provider never selected
P08 — All allowed providers fail → controlled error
```

## Usage reporting

```text
R01 — Store total usage correct
R02 — Provider breakdown correct
R03 — Model breakdown correct
R04 — Prompt/completion totals correct
R05 — Billing period correct
R06 — Store isolation correct
R07 — Upgrade does not reset usage
R08 — New billing period starts new quota period
```

## Integration

```text
I01 — Trusted plan received from .NET
I02 — Browser cannot override plan
I03 — Browser cannot override provider
I04 — Browser cannot override model
I05 — billing period received correctly
I06 — renewal date handled correctly
I07 — session ID propagated correctly
```

---

# 48. CONCURRENCY TEST — REQUIRED

Create a test that launches many concurrent requests against:

```text
store token reservation
```

with a quota that is intentionally close to exhaustion.

Example:

```text
Limit = 1,000
Available = 100

20 concurrent requests
each reserves 20
```

Only five reservations may succeed.

The final reserved/used amount must never exceed:

```text
1,000
```

Repeat equivalent testing for:

```text
consumer daily message limit = 15
```

with concurrent requests.

---

# 49. FAILURE TESTS

Test:

```text
Redis unavailable
LLM provider unavailable
provider API quota exhausted
all allowed providers unavailable
Mongo unavailable
invalid plan context
missing billing period
missing session ID
invalid store context
```

Commercial quota enforcement must never silently become unlimited.

---

# 50. REQUIRED REPORT

Create:

```text
docs/audit/AI-USAGE-QUOTA-IMPLEMENTATION-REPORT.md
```

Include:

1. Existing AI architecture
2. Plan context contract
3. Token quota architecture
4. Billing-period architecture
5. Reservation algorithm
6. Redis keys
7. Atomicity guarantees
8. Token calculation
9. Consumer session quota
10. Provider selection
11. Provider failover
12. Model policy
13. Usage persistence
14. Usage reporting
15. Provider breakdown
16. Model breakdown
17. Quota-exceeded behavior
18. Tenant isolation
19. Concurrency tests
20. Failure tests
21. API changes
22. Files changed
23. Tests executed
24. Regression results
25. Performance impact
26. Security impact
27. Out-of-scope items
28. Remaining risks

---

# 51. FRONTEND/DASHBOARD CONTRACT

The store owner's dashboard needs:

```text
Current Plan
Billing Period
Token Limit
Tokens Used
Tokens Remaining
Usage Percentage
Renewal Date
Provider Usage
Model Usage
Consumer Daily Limit
```

The consumer/widget needs only safe runtime responses.

It must NOT receive:

```text
provider API key
internal provider health
plan configuration internals
other stores' usage
other consumers' usage
```

---

# 52. STORE OWNER CONSUMER LIMIT API

The store owner should be able to configure:

```text
consumer_daily_message_limit
```

through the existing store settings/API architecture.

Do not create a Super Admin endpoint for this.

Validation:

```text
requested_limit >= 0
requested_limit <= plan.consumer_daily_message_limit_max
```

Use the existing authorization rules to ensure the merchant can modify only their own authorized store.

---

# 53. QUOTA-EXCEEDED UX

When store quota is exhausted:

Consumer:

```text
This store has reached its AI usage limit for the current billing period.
```

Store owner:

```text
AI usage limit reached.

Used:
1,000,000 / 1,000,000

Renewal:
<renewal date>
```

Do not expose internal implementation details.

---

# 54. NO USAGE RESET ON UPGRADE

Explicit rule:

```text
Upgrade
   ↓
Do not delete historical usage
   ↓
Do not set used = 0
   ↓
Update entitlement
```

If the billing period does not change, usage remains in the same period.

---

# 55. NEW PERIOD

At the next Stripe subscription billing period:

```text
Old period
   ↓
close
   ↓
New period
   ↓
new entitlement
   ↓
new quota accounting period
```

Historical usage remains queryable.

---

# 56. DOWNGRADE

Do NOT implement downgrade logic in FastAPI.

.NET/Stripe controls it.

FastAPI simply receives the new authoritative plan when the new billing period begins.

---

# 57. NO CALENDAR-MONTH LOGIC

Do NOT write:

```python
datetime.now().strftime("%Y-%m")
```

as the commercial quota identity unless the .NET billing contract explicitly provides a calendar-month subscription.

The quota period must derive from the subscription billing period.

---

# 58. STRICT ARCHITECTURAL BOUNDARY

Final responsibility matrix:

```text
.NET
│
├── Subscription
├── Stripe
├── Billing cycle
├── Renewal date
├── Trial days
├── Plan
├── Plan token limit
├── Plan provider policy
├── Plan model policy
└── Plan consumer maximum
        │
        ▼
Trusted AI Context
        │
        ▼
FASTAPI
│
├── Runtime quota enforcement
├── Atomic reservation
├── Actual token accounting
├── Consumer/session quota
├── Provider selection
├── Provider failover
├── Model selection
├── Usage aggregation/reporting
└── AI execution
```

Do not reverse these responsibilities.

---

# 59. FINAL ACCEPTANCE CRITERIA

```text
[ ] Plan context comes from trusted .NET service
[ ] No browser-controlled plan
[ ] Store token quota implemented
[ ] Quota uses Stripe subscription billing period
[ ] Renewal date respected
[ ] Calendar-month quota is NOT used
[ ] Pre-flight quota check exists
[ ] Atomic Redis reservation exists
[ ] Concurrent store requests cannot exceed quota
[ ] Actual provider token usage calculated
[ ] Prompt + completion tokens normalized
[ ] Reservation reconciled with actual usage
[ ] Unused reservation released
[ ] Consumer quota uses session_id
[ ] Anonymous consumers are counted
[ ] Consumer quota is store isolated
[ ] Consumer reservation is atomic
[ ] Store owner controls consumer limit
[ ] Consumer limit cannot exceed plan maximum
[ ] Super Admin controls plan maximum
[ ] Provider policy centrally managed
[ ] Model policy centrally managed
[ ] Consumer cannot select provider
[ ] Consumer cannot select model
[ ] Provider API failure triggers allowed-provider fallback
[ ] Provider quota exhaustion triggers allowed-provider fallback
[ ] Disallowed provider is never selected
[ ] All providers unavailable returns controlled error
[ ] Store quota exceeded returns controlled response
[ ] Consumer quota exceeded returns controlled response
[ ] Usage reporting API exists/extended
[ ] Usage progress information available
[ ] Provider usage breakdown available
[ ] Model usage breakdown available
[ ] Tenant isolation verified
[ ] Plan upgrade does not reset usage
[ ] Downgrade remains controlled by .NET until renewal
[ ] New billing period gets new entitlement
[ ] Existing rate limiter remains intact
[ ] Existing AI/RAG/widget architecture remains intact
[ ] Existing provider abstraction remains intact
[ ] Existing tests pass
[ ] New tests pass
[ ] Concurrency tests pass
[ ] Failure tests pass
```

---

# 60. STRICT STOP RULE

After all acceptance criteria pass:

**STOP.**

Do not implement:

- additional billing features
- automatic upgrades
- automatic downgrades
- payment handling
- new subscription endpoints
- new provider integrations
- new AI features
- new widget features
- new analytics features unrelated to usage
- token storage architecture
- unrelated refactoring

If you discover a conflict between:

```text
existing architecture
```

and:

```text
this specification
```

**STOP BEFORE CHANGING THE CONFLICTING DESIGN.**

Report:

```text
CONFLICT DETECTED

Existing behavior:
...

Requested behavior:
...

Affected component:
...

Risk:
...

Recommended options:
...
```

Wait for architectural decision.

Do not silently choose an implementation.

---

# FINAL OBJECTIVE

The final AI execution flow must be:

```text
AI Request
    ↓
Trusted .NET subscription context
    ↓
Resolve Store + Plan + Billing Period
    ↓
Resolve Plan Policy
    ↓
Check Consumer Session Limit
    ↓
Check Store Token Quota
    ↓
Atomic Token Reservation
    ↓
Automatic Provider/Model Selection
    ↓
LLM Execution
    │
    ├── Success
    │      ↓
    │   Actual token usage
    │      ↓
    │   Commit usage
    │      ↓
    │   Release unused reservation
    │
    └── Provider failure
           ↓
       Release/adjust reservation
           ↓
       Select another allowed provider
           ↓
       Retry execution within existing request policy
    ↓
Usage Logging
    ↓
Usage Aggregation
    ↓
Response
```

Consumer enforcement:

```text
Store
 +
Session ID
 +
Day
     ↓
Atomic message reservation
     ↓
Allowed
     ↓
AI execution

OR

Limit reached
     ↓
CONSUMER_DAILY_LIMIT_EXCEEDED
```

Store enforcement:

```text
Store
 +
Stripe Billing Period
     ↓
Atomic token reservation
     ↓
Allowed
     ↓
AI execution

OR

Quota exhausted
     ↓
STORE_TOKEN_QUOTA_EXCEEDED
```

**Implement exactly this architecture, preserve the existing AI Commerce design, and do not add any feature or architectural change outside this specification.**