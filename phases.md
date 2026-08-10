# AI Commerce FastAPI — Production Audit, Testing & Safe Hardening Execution Plan

You are acting as a **Staff Software Architect, Senior Backend Engineer, Security Engineer, QA Engineer, and Production Reliability Engineer**.

You are working on the existing **AI Commerce FastAPI AI Service**.

Your task is NOT to rewrite the system.

Your task is to:

> **Audit the current implementation → execute the recommended test plan → identify real failures → fix only necessary issues → verify regressions → produce a detailed implementation/test report.**

The system is already partially implemented.

The current architecture includes:

```text
React
   ↓
ASP.NET Core
   ↓
SQL Server

ASP.NET Core
   ↓
FastAPI AI Service
   ↓
MongoDB / Vector Search
   ↓
LLM Providers
```

The architecture defines FastAPI as the AI service responsible for RAG, AI execution and AI-oriented MongoDB/vector operations, while ASP.NET Core remains responsible for SaaS/business-domain logic and SQL Server. Preserve this boundary.

The current OpenAPI schema already contains:

* AI APIs
* AI streaming
* RAG APIs
* knowledge management
* conversations
* recommendations
* widget installation
* widget bootstrap
* widget chat
* widget recommendations
* products
* prompts
* jobs
* connections
* analytics-related APIs
* other existing functionality

Do NOT assume anything is missing simply because it is not part of the future plan.

---

# 1. ABSOLUTE RULES

## RULE 1 — DO NOT BREAK THE EXISTING SYSTEM

Do not:

* rewrite the FastAPI service
* replace frameworks
* replace MongoDB
* replace vector storage
* replace Redis
* replace LLM providers
* replace authentication
* replace the RAG engine
* replace the current repository implementation
* replace existing widget implementation
* change ASP.NET Core architecture
* change SQL ownership
* remove existing APIs
* rename existing APIs unnecessarily
* change existing request/response contracts unnecessarily
* perform destructive migrations
* change production behavior without evidence

---

# 2. SOURCE OF TRUTH

Use this priority order:

1. Current source code
2. Current tests
3. Current OpenAPI schema
4. Existing database/schema implementation
5. Existing architecture documents
6. This execution plan

Do NOT blindly implement something from an old architecture document if the current implementation already solves the requirement differently.

For example:

The existing system has:

```text
ai_settings
ModelRegistry
Prompt key/version/is_active
```

Do NOT automatically create:

```text
PromptResolver
AIExecutionPolicy
```

unless the audit proves that the current implementation cannot satisfy the required behavior.

The same applies to internal service authentication.

---

# 3. CURRENT KNOWN STATUS

The following has already been reported and MUST be verified against the actual code.

| Capability                      | Expected current status  |
| ------------------------------- | ------------------------ |
| TenantContext                   | Implemented              |
| User actor                      | Implemented              |
| Widget actor                    | Implemented              |
| Widget lifecycle                | Implemented              |
| Widget key hashing              | Implemented              |
| Widget scopes                   | Implemented              |
| Widget bootstrap                | Implemented              |
| Origin validation               | Implemented              |
| Short-lived widget JWT          | Implemented              |
| Bootstrap cache                 | Implemented              |
| Widget chat                     | Implemented              |
| Widget recommendations          | Implemented              |
| Conversation store isolation    | Implemented              |
| Knowledge namespace isolation   | Implemented but untested |
| Request correlation             | Partial                  |
| X-Request-ID                    | Missing                  |
| Runtime correlation propagation | Partial                  |
| Rate limiting                   | Global per-IP            |
| Endpoint/session rate limits    | Missing                  |
| Internal service authentication | Partial                  |
| OpenAPI baseline                | Missing                  |
| Endpoint ownership matrix       | Missing                  |
| Repository tenant audit         | Incomplete               |
| PromptResolver                  | Missing                  |
| AIExecutionPolicy               | Missing                  |
| Widget streaming                | Missing                  |
| Widget events                   | Missing                  |
| Attribution                     | Missing                  |
| Explicit widget sessions        | Incomplete               |
| Cross-store tests               | Missing                  |
| Prompt injection tests          | Missing                  |
| RAG leakage tests               | Missing                  |

Do not trust this table blindly.

Verify everything.

---

# 4. EXECUTION STRATEGY

Execute in this exact order:

```text
PHASE A
Baseline & Inventory
        ↓
PHASE B
Observability & Correlation
        ↓
PHASE C
Tenant Isolation & Security Testing
        ↓
PHASE D
Rate Limiting
        ↓
PHASE E
Widget Streaming
        ↓
PHASE F
Widget Events & Attribution
        ↓
PHASE G
Final Regression & Production Audit
```

Do not skip a phase.

Do not start a later phase if an earlier security gate fails.

---

# PHASE G — FINAL PRODUCTION AUDIT

After all implementation work:

---

## G1. Full regression suite

Run:

```text
unit tests
integration tests
repository tests
API tests
authentication tests
authorization tests
RAG tests
vector tests
Mongo tests
Redis tests
widget tests
streaming tests
rate-limit tests
event tests
```

---

# G2. OpenAPI compatibility

Compare:

```text
docs/api/openapi-baseline.json
```

against the final schema.

Classify every difference:

```text
NON-BREAKING
INTENTIONAL BREAKING
UNINTENTIONAL BREAKING
```

Any:

```text
UNINTENTIONAL BREAKING
```

is a release blocker.

---

# G3. Security audit

Verify:

```text
tenant isolation
authentication
authorization
origin validation
widget token expiration
widget token scopes
rate limiting
prompt injection resistance
secret exposure
PII logging
CORS
```

---

# G4. Failure testing

Test:

```text
Mongo unavailable
Redis unavailable
Vector DB unavailable
LLM unavailable
LLM timeout
LLM rate limit
embedding failure
document processing failure
stream disconnect
invalid widget key
expired widget token
disabled widget
```

Expected behavior must be controlled and must never bypass tenant isolation.

---

# G5. Performance

Measure:

```text
bootstrap P50/P95/P99
chat P50/P95/P99
stream start latency
recommendation P50/P95/P99
RAG retrieval latency
vector search latency
Mongo latency
LLM latency
```

Do not optimize blindly.

Record the actual measurements.

---

# G6. Production readiness checklist

Verify:

```text
[ ] No destructive migrations
[ ] No broken existing API
[ ] No broken widget
[ ] No broken RAG
[ ] No broken AI providers
[ ] No tenant leakage
[ ] No secret leakage
[ ] No uncontrolled LLM parameters from widget
[ ] Rate limiting enabled
[ ] Request correlation enabled
[ ] Runtime logging correlated
[ ] Streaming tested
[ ] Events tested
[ ] Attribution tested
[ ] OpenAPI baseline updated
[ ] Regression suite passes
[ ] Rollback strategy documented
```

---

# 5. REQUIRED REPORTING FORMAT

After EVERY phase, produce a report.

Do not simply say:

```text
Done.
```

Use:

````text
# Phase X Report

## 1. Status

PASS / PASS WITH WARNINGS / BLOCKED

## 2. What Was Audited

List exact components.

## 3. What Was Changed

List exact files and changes.

## 4. What Was NOT Changed

Explicitly state preserved architecture/components.

## 5. Tests Executed

| ID | Test | Result | Evidence |
|---|---|---|---|
| C-01 | Store A conversation | PASS | ... |
| C-02 | Store A → Store B | PASS | ... |

## 6. Failures Found

For every failure:

- test ID
- component
- expected behavior
- actual behavior
- severity
- root cause

## 7. Fixes Applied

For every fix:

- problem
- change
- files
- reason
- compatibility impact

## 8. Security Impact

Explain whether security posture improved, unchanged, or degraded.

## 9. Production Impact

Explain whether production behavior changed.

## 10. API Impact

List:

- added endpoints
- modified endpoints
- deprecated endpoints
- unchanged endpoints
- breaking changes

## 11. Database Impact

List:

- schema changes
- indexes
- migrations
- data migrations

If none:

```text
No database changes.
````

## 12. Remaining Risks

List every unresolved issue.

## 13. Required Action

For each unresolved issue:

| Issue | Severity | Action | Owner | Blocking? |
| ----- | -------- | ------ | ----- | --------- |

## 14. Exit Gate

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

````

---

# 6. SEVERITY CLASSIFICATION

Use:

### P0 — Critical

Examples:

```text
cross-store data leakage
authentication bypass
tenant impersonation
secret exposure
destructive production migration
````

Action:

```text
STOP
```

---

### P1 — High

Examples:

```text
RAG isolation failure
widget authorization failure
uncontrolled LLM cost
major production regression
```

Action:

```text
BLOCK RELEASE
```

---

### P2 — Medium

Examples:

```text
missing observability
incomplete attribution
missing endpoint rate limit
non-critical API inconsistency
```

Action:

```text
Fix before production if practical
or explicitly accept risk
```

---

### P3 — Low

Examples:

```text
documentation gap
minor schema cleanup
non-critical optimization
```

Action:

```text
Backlog
```

---

# 7. ACTION REPORT

At the end of the complete audit, create:

```text
docs/audit/FINAL-AUDIT-REPORT.md
```

It must contain:

```text
# AI Commerce FastAPI Production Audit

## Executive Summary

## Current Architecture

## Phase Results

### Phase A
### Phase B
### Phase C
### Phase D
### Phase E
### Phase F
### Phase G

## Test Summary

Total tests:
Passed:
Failed:
Skipped:
Blocked:

## Security Findings

P0:
P1:
P2:
P3:

## Production Findings

## API Compatibility

## Database Changes

## Performance Results

## Observability

## Remaining Risks

## Required Actions

## Release Recommendation

GO
GO WITH WARNINGS
NO-GO

## Final Decision
```

---

# 8. IMPORTANT — DO NOT HIDE FAILURES

If something fails, report it.

Do NOT:

* weaken the test
* remove the test
* change expected behavior just to pass
* mark a failure as warning without justification
* silently skip tests
* modify production behavior to hide a regression

If a failure is caused by an existing architectural decision:

Document:

```text
Existing behavior
↓
Why it conflicts
↓
Risk
↓
Minimum safe solution
```

---

# 9. IMPORTANT — DO NOT OVER-IMPLEMENT

If you discover:

```text
PromptResolver not required
```

do not create it.

If:

```text
AIExecutionPolicy
```

is already effectively provided by:

```text
ai_settings + ModelRegistry
```

do not duplicate it.

If:

```text
existing JWT
```

is sufficient for internal authentication:

do not create another authentication system.

If:

```text
existing namespace isolation
```

is secure after testing:

do not redesign the vector architecture.

The goal is:

> **Prove the current architecture is safe first. Change only what the evidence proves must change.**

---

# 10. FINAL NON-NEGOTIABLE PRINCIPLE

The implementation must preserve:

```text
Existing Architecture
        +
Existing APIs
        +
Existing AI Providers
        +
Existing RAG
        +
Existing MongoDB
        +
Existing Widget
        +
Existing Production Behavior
```

while adding:

```text
Strong Tenant Isolation
+
Request Correlation
+
Endpoint Rate Limits
+
Widget Streaming
+
Widget Events
+
Attribution
+
Security Tests
+
Production Evidence
```

The final system must follow:

```text
                    STOREFRONT
                         │
                         ▼
                    Widget API
                         │
                    Widget Token
                         │
                         ▼
                  TenantContext
                         │
                 ┌───────┴───────┐
                 │               │
          organization_id     store_id
                 │               │
                 └───────┬───────┘
                         ▼
                 Application Layer
                         │
                 ┌───────┼────────┐
                 ▼       ▼        ▼
                RAG     AI      Recommendations
                 │       │        │
                 └───────┼────────┘
                         ▼
                  Mongo / Vector
                         │
                         ▼
                       LLM
```

The **server-derived `store_id` remains the canonical AI tenant boundary**.

The client/widget may provide:

```text
customer_id
session_id
conversation_id
page context
product context
```

but must never be trusted to define:

```text
organization_id
store_id
widget ownership
```

---

# 11. FINAL INSTRUCTION TO THE AGENT

Start with **Phase A only**.

Do not implement Phase B until Phase A is complete and reported.

Do not implement Phase C until Phase B is complete and reported.

Do not implement Phase D until Phase C passes all tenant-isolation gates.

Do not implement Phase E until Phase D passes.

Do not implement Phase F until Phase E passes.

Do not implement Phase G until all previous phases are complete.

At the end of each phase:

1. Stop.
2. Run the required tests.
3. Generate the phase report.
4. State PASS / PASS WITH WARNINGS / BLOCKED.
5. List exactly what needs action.
6. Continue only if the exit gate allows it.

**Never sacrifice production stability or tenant security to complete the roadmap faster.**
