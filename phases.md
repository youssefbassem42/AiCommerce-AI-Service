# AI Commerce FastAPI — Integration JWT Decode + E-commerce Authentication + Sync Now

## STRICT IMPLEMENTATION SPECIFICATION

You are acting as a:

* Senior Software Architect
* Senior FastAPI Engineer
* Integration Engineer
* Security Engineer
* QA Engineer

You are modifying the existing **AI Commerce FastAPI AI Service**.

Your task is strictly limited to the exact flow defined in this document.

---

# 1. ABSOLUTE RULE — DO NOT EXPAND SCOPE

You MUST implement ONLY the requirements explicitly defined in this prompt.

Do NOT add, redesign, refactor, or introduce any feature that is not explicitly requested.

Do NOT:

* redesign the integration architecture
* redesign authentication
* redesign JWT structure
* store the e-commerce JWT
* add refresh-token storage
* add OAuth
* add service accounts
* add token rotation
* add credential rotation
* add background authentication workers
* add scheduled authentication
* add connection-health architecture
* add new synchronization stages
* add new AI/RAG features
* add widget features
* add new promo-code features
* add discount calculation
* add maximum-discount logic
* add coupon generation
* create new collections unnecessarily
* create duplicate services
* create duplicate repositories
* rewrite existing synchronization
* rewrite existing OpenAPI parsing
* rewrite existing tenant isolation
* modify unrelated endpoints

If you discover a possible improvement:

> **DO NOT IMPLEMENT IT.**

Record it only under:

```text
OUT OF SCOPE / FUTURE WORK
```

---

# 2. EXACT BUSINESS OBJECTIVE

The current AI Commerce .Net service encoded JWT already contains:

```text
E-commerce Admin Email
E-commerce Admin Password
```

The required behavior is:

```text
AI Commerce Fetch JWT
       ↓
Decode JWT
       ↓
Extract E-commerce Admin Email
Extract E-commerce Admin Password
       ↓
Authenticate/Login to E-commerce
       ↓
Obtain temporary/current E-commerce authentication
       ↓
Fetch required data
       ↓
Store existing synchronized data
```

The resulting e-commerce JWT/access token:

> **MUST NOT be persisted in our service.**

It may exist only in memory/current execution for the required e-commerce API operations.

---

# 3. REQUIRED NEW RETRY BEHAVIOR

The ONLY additional architecture being introduced by this task is:

> **Retry e-commerce login a maximum of 3 times using the credentials extracted from the AI Commerce JWT.**

The exact behavior is:

```text
Decode AI Commerce JWT
        ↓
Extract email/password
        ↓
Login Attempt #1
        ↓
Failed
        ↓
Login Attempt #2
        ↓
Failed
        ↓
Login Attempt #3
        ↓
Failed
        ↓
STOP
```

Maximum:

```text
3 login attempts
```

No fourth attempt.

No infinite retry.

No exponential background retry.

No scheduled retry.

No retry worker.

No automatic retry after the operation has returned an error.

---

# 4. LOGIN RETRY RULE

The three attempts MUST use the same credentials extracted from the current AI Commerce JWT.

Conceptually:

```python
for attempt in range(1, 4):
    try:
        ecommerce_auth = login(email, password)

        if successful:
            break

    except AuthenticationError:
        if attempt == 3:
            raise IntegrationAuthenticationError(...)
```

However:

> First inspect the existing integration authentication implementation and follow its existing patterns.

Do not blindly copy this pseudocode.

---

# 5. DO NOT RETRY EVERYTHING

The retry mechanism is specifically for:

> **E-commerce login/authentication failure.**

Do NOT retry:

* order fetching
* customer fetching
* product fetching
* database writes
* MongoDB operations
* OpenAPI parsing
* capability detection
* arbitrary HTTP failures

unless the existing architecture already has such behavior.

The requested retry is:

```text
LOGIN ONLY
```

---

# 6. LOGIN FAILURE AFTER THREE ATTEMPTS

If all three login attempts fail:

```text
Attempt 1 → FAILED
Attempt 2 → FAILED
Attempt 3 → FAILED
```

the operation MUST STOP.

Do NOT continue to:

```text
/orders
/customers
```

Do NOT attempt to fetch any protected e-commerce data if not pritected fetch them as the previous behaviour.

Do NOT partially continue synchronization.

Return a clear integration authentication error.

The user-facing meaning must be:

> **The e-commerce admin email or password is incorrect. Orders, customers, and other protected store data could not be fetched. Please update the e-commerce integration credentials in the Admin Panel and try again.**

---

# 7. REQUIRED ERROR SEMANTICS

The exact HTTP status must follow the existing API error conventions.

Do not invent a new error framework.

The error must clearly communicate:

```text
Authentication with the e-commerce system failed after 3 attempts.
The configured admin email/password may be incorrect.
No protected store data was fetched.
Update the integration credentials in the Admin Panel and try again.
```

Do NOT expose:

```text
actual password
JWT
Authorization header
internal authentication response
stack trace
```

---

# 8. IMPORTANT — DO NOT SAY THE PASSWORD IS DEFINITELY WRONG

The implementation cannot always prove that the password itself is wrong.

Therefore the backend error should preferably communicate:

> **E-commerce authentication failed. Please verify that the configured admin email and password are correct.**

Do not falsely claim:

> "The password is definitely wrong."

The actual login failure could theoretically be caused by another authentication issue.

The UI/message can explain that the configured email/password should be checked.

---

# 9. REQUIRED USER RECOVERY FLOW

After three failed login attempts:

```text
Sync Now
   ↓
Authentication failed
   ↓
STOP
```

The user must be instructed to:

```text
Admin Panel
   ↓
Integration
   ↓
Update E-commerce Admin Email/Password
   ↓
Save / Complete Integration
   ↓
Try Again
```

The backend MUST NOT automatically retry later.

The user explicitly retries after correcting the integration credentials.

---

# 10. REQUIRED SYNC NOW FLOW

The existing Sync Now flow includes connection creation.

Preserve this behavior.

The required flow is:

```text
USER CLICKS "SYNC NOW"
        ↓
POST /api/v1/integration/connections
        ↓
Decode AI Commerce JWT
        ↓
Extract E-commerce Admin Email
Extract E-commerce Admin Password
        ↓
E-commerce Login Attempt #1
        ↓
Failure?
        ↓
E-commerce Login Attempt #2
        ↓
Failure?
        ↓
E-commerce Login Attempt #3
        ↓
Success?
       / \
     YES  NO
      │    │
      │    └──────────────→ STOP
      │                     ↓
      │                 Return error
      │                     ↓
      │                 NO DATA FETCH
      │
      ▼
Create Connection
      ↓
POST /api/v1/integration/connections/{connection_id}/sync
      ↓
Decode AI Commerce JWT
      ↓
Extract E-commerce credentials
      ↓
E-commerce Login
      ↓
Check Promo Code capability
      ↓
Fetch existing required data
      ↓
Store existing synchronized data
```

Do not add additional stages.

---

# 11. IMPORTANT: FETCH DATA THAT PUBLIC NOT REQUIRE AUTHENTICATION OR 401 ERROR IF AUTHENTICATION FAILD SKIP THESE ENDPOINTS AND RETURN ERROR TO CHECK ADMIN PANEL EMAIL AND PASSWORD VALIDATION

This is a hard rule.

The system MUST NOT execute any endpoints that require admin role in e-commerce:

```text
/orders
/customers
```

before successful e-commerce authentication.

Correct:

```text
LOGIN SUCCESS
    ↓
FETCH DATA
```

Incorrect:

```text
FETCH ORDERS
    ↓
401
    ↓
TRY LOGIN
```

The login must happen first for the requested flow.

---

# 12. REQUIRED ENDPOINT #1

Audit and modify:

```http
POST /api/v1/integration/connections
```

The endpoint must:

1. Authenticate the AI Commerce request.
2. Resolve the current tenant/store using the existing architecture.
3. Decode the AI Commerce JWT.
4. Extract e-commerce admin email.
5. Extract e-commerce admin password.
6. Attempt e-commerce login.
7. Retry login up to 3 times if authentication fails.
8. Stop immediately after successful authentication.
9. If all 3 attempts fail, fetch public data but DO NOT DUPLICATE DATA and return the integration authentication error.
10. If successful, continue the EXISTING connection creation flow.
11. Do not persist the resulting e-commerce JWT.

---

# 13. REQUIRED ENDPOINT #2

Audit and modify:

```http
POST /api/v1/integration/connections/{connection_id}/sync
```

The endpoint must:

1. Authenticate the AI Commerce request.
2. Validate the connection belongs to the authenticated store.
3. Decode the AI Commerce JWT.
4. Extract e-commerce admin email/password.
5. Authenticate with the e-commerce system.
6. Retry login up to 3 times.
7. Stop if authentication fails after 3 attempts.
8. Do NOT fetch orders/customers or any endpoints that require admin role after failed authentication.
9. If authentication succeeds, continue the existing synchronization logic.
10. Check Promo Code capability.
11. Update `store_capabilities.has_promo_code`.
12. Fetch the existing required entities.
13. Store them using the existing storage pipeline and make sure not duplicating data.
14. Return the existing sync response format.

---

# 14. E-COMMERCE JWT MUST NOT BE STORED

The e-commerce login may return:

```text
access_token
JWT
token
session token
```

Use it only for the current operation.

Do NOT:

* save it in MongoDB
* save it in SQL
* save it in Redis
* put it in StoreIntegration
* put it in AI Commerce JWT
* return it to frontend
* log it

The e-commerce authentication token is temporary/current-operation state.

---

# 15. AI COMMERCE JWT

The AI Commerce JWT remains the source of:

```text
TenantContext
+
E-commerce Admin Email
+
E-commerce Admin Password
```

Conceptually:

```text
AI Commerce JWT
│
├── user identity
├── organization identity
├── store identity
├── roles/scopes
│
├── e-commerce admin email
└── e-commerce admin password
```

Do not change this architecture unless the current implementation literally lacks the required claims.

---

# 16. TENANT ISOLATION MUST NOT CHANGE

The decoded e-commerce credentials are NOT tenant identifiers.

Tenant identity remains derived from the existing authenticated AI Commerce context.

```text
AI Commerce JWT
       │
       ├── TenantContext
       │     ├── organization_id
       │     └── store_id
       │
       └── E-commerce credentials
             ├── email
             └── password
```

Never use e-commerce JWT claims to override:

```text
store_id
organization_id
widget_id
```

---

# 17. JWT DECODING

Inspect the existing JWT implementation first.

Find:

* existing decoder
* authentication middleware
* JWT utilities
* claim definitions
* current credential claims

Reuse existing implementation.

Do not create duplicate JWT utilities.

Extract only the actual claim names used by the current system.

Do not invent claim names.

---

# 18. E-COMMERCE LOGIN

Inspect the current integration implementation/OpenAPI configuration to determine the actual e-commerce authentication endpoint.

Do not assume:

```text
/login
/auth/login
/api/login
```

or any other URL.

Use the existing integration configuration/discovery.

The credentials must be:

```text
email
password
```

from the decoded AI Commerce JWT.

---

# 19. PROMO CODE CAPABILITY

During the requested connection/sync flow, determine whether the connected e-commerce system provides a Promo Code service.

Use the existing integration/OpenAPI discovery mechanisms.

Do not introduce a new discovery architecture.

Existing collection:

```text
store_capabilities
```

Existing field:

```text
has_promo_code: boolean
```

---

# 20. UPDATE PROMO CAPABILITY

If Promo Code service exists:

```text
has_promo_code = true
```

If Promo Code service does not exist:

```text
has_promo_code = false
```

Update the capability for the correct store only.

Do not create a new collection.

Do not create a second capability flag.

Do not implement promo-code creation or discount logic.

---

# 21. CAPABILITY FAILURE

If capability discovery itself fails:

Do NOT silently claim:

```text
has_promo_code = false
```

unless the existing business logic explicitly defines failure as false.

Preserve the existing capability state if that is the current architecture's behavior.

Do not introduce an `UNKNOWN` state unless the existing model already supports it.

This task only requires the existing boolean to be correctly updated when capability detection succeeds.

---

# 22. EXISTING DATA SYNCHRONIZATION

Once authentication succeeds, continue the existing synchronization implementation.

Do NOT change the existing list of synchronized entities.

Do NOT introduce new entities.

Do NOT redesign canonical models.

Do NOT redesign repositories.

Do NOT redesign MongoDB collections.

The only authentication change is:

```text
Decode JWT
 ↓
Extract credentials
 ↓
Login
 ↓
Maximum 3 attempts
 ↓
Successful login
 ↓
Existing synchronization
```

---

# 23. SECURITY — NEVER LOG CREDENTIALS

Never log:

```text
AI Commerce JWT
E-commerce password
E-commerce JWT
Authorization header
Full login request
```

Safe logging may include:

```text
connection_id
store_id
authentication attempt number
authentication succeeded/failed
sync started
sync completed
```

Example:

```text
E-commerce authentication attempt 1 failed for connection <id>
```

Do NOT include the email if existing logging policy treats it as sensitive.

---

# 24. RETRY LOGGING

The implementation may log:

```text
attempt = 1
attempt = 2
attempt = 3
```

but never:

```text
password
JWT
Authorization header
```

After attempt 3:

```text
E-commerce authentication failed after 3 attempts.
```

Then stop.

---

# 25. NO RETRY AFTER THREE FAILURES

After:

```text
Attempt 1 → fail
Attempt 2 → fail
Attempt 3 → fail
```

the operation ends.

Do NOT:

```text
sleep
retry later
queue another login
schedule another login
spawn worker
refresh in background
```

The user must correct the integration configuration and explicitly click:

```text
Try Again
```

---

# 26. ADMIN PANEL RECOVERY

The intended recovery is:

```text
Authentication Failed
        ↓
Admin Panel
        ↓
Integration
        ↓
Correct E-commerce Admin Email
Correct E-commerce Admin Password
        ↓
Save / Complete Integration
        ↓
Try Again
```

Do not implement additional recovery mechanisms.

The backend only needs to return a clear error that enables the frontend to communicate this recovery path.

---

# 27. ERROR RESPONSE REQUIREMENT

Use the existing API error response format.

The error must communicate:

```text
E-commerce authentication failed after 3 attempts.

The configured e-commerce admin email/password could not authenticate.

Orders, customers, and other protected store data were NOT fetched.

Please update the e-commerce integration credentials in the Admin Panel and try again.
```

Do not expose credentials or internal details.

---

# 28. TESTS — ONLY REQUIRED TESTS

Add tests for exactly this functionality.

## JWT

```text
T01 — Decode valid AI Commerce JWT
T02 — Extract e-commerce email
T03 — Extract e-commerce password
T04 — Missing credentials fails safely
T05 — Invalid JWT fails safely
```

## Login Retry

```text
T06 — Login succeeds on attempt 1
T07 — Login fails once then succeeds on attempt 2
T08 — Login fails twice then succeeds on attempt 3
T09 — Login fails three times
T10 — Fourth login attempt NEVER occurs
```

## Failure Behavior

```text
T11 — Three failed logins return integration authentication error
T12 — Orders are NOT fetched after three login failures
T13 — Customers are NOT fetched after three login failures
T14 — Products are NOT fetched after three login failures
T15 — No synchronization data is stored after authentication failure
```

## Success Behavior

```text
T16 — Successful login continues existing connection flow
T17 — Successful login continues existing sync flow
T18 — Existing synchronized data is stored normally
```

## Promo Capability

```text
T19 — Promo Code service detected
T20 — Promo Code service absent
T21 — has_promo_code=true persisted
T22 — has_promo_code=false persisted
T23 — Store A cannot modify Store B capability
```

## Regression

```text
T24 — Existing connection tests pass
T25 — Existing sync tests pass
T26 — Existing integration tests pass
```

---

# 29. TEST THE EXACT RETRY SEQUENCE

The most important test is:

```text
Attempt 1 → authentication failure
Attempt 2 → authentication failure
Attempt 3 → authentication failure
        ↓
STOP
        ↓
Error returned
        ↓
NO /orders
NO /customers
NO /products
NO database synchronization
```

And:

```text
Attempt 1 → failure
Attempt 2 → success
        ↓
STOP RETRYING
        ↓
Continue synchronization
```

Do NOT execute attempt 3 after attempt 2 succeeds.

---

# 30. CONNECTION + SYNC SEQUENCE

Verify the exact sequence:

```text
Sync Now
   ↓
Create Connection
   ↓
Decode JWT
   ↓
Extract credentials
   ↓
Login
   ↓
Retry max 3
   ↓
Success
   ↓
Sync
   ↓
Capability detection
   ↓
Store data
```

Do not introduce additional stages.

---

# 31. FILE CHANGE RULE

Before editing any file:

1. Search for existing implementation.
2. Understand current dependency flow.
3. Modify the smallest possible area.
4. Preserve existing public contracts where possible.
5. Do not refactor unrelated code.

After editing:

```text
git diff
```

must be reviewed.

Look specifically for accidental changes outside:

```text
JWT decoding
integration authentication
connection creation
sync authentication
promo capability update
tests
documentation/report
```

---

# 32. REQUIRED FINAL REPORT

Generate:

```text
docs/audit/INTEGRATION-JWT-SYNC-RETRY-REPORT.md
```

The report must contain:

## 1. Executive Summary

## 2. Exact Flow Implemented

## 3. AI Commerce JWT Decoding

## 4. E-commerce Authentication

## 5. Three-Attempt Retry Mechanism

## 6. Connection Endpoint Changes

```text
POST /api/v1/integration/connections
```

## 7. Sync Endpoint Changes

```text
POST /api/v1/integration/connections/{connection_id}/sync
```

## 8. Promo Code Capability Detection

## 9. `store_capabilities.has_promo_code`

## 10. Authentication Failure Behavior

## 11. Data Fetch Prevention After Authentication Failure

## 12. Tenant Isolation

## 13. Security

## 14. Files Changed

## 15. Tests Added

## 16. Tests Executed

## 17. Test Results

## 18. Regression Results

## 19. Out-of-Scope Items Not Implemented

## 20. Frontend/Admin Panel Behavior Required

---

# 33. FINAL ACCEPTANCE CRITERIA

The implementation is complete ONLY if:

```text
[ ] Existing AI Commerce JWT is decoded
[ ] E-commerce admin email is extracted
[ ] E-commerce admin password is extracted
[ ] Credentials are used for e-commerce login
[ ] E-commerce JWT/access token is NOT persisted
[ ] Login has maximum 3 attempts
[ ] Attempt 2 happens only after attempt 1 fails
[ ] Attempt 3 happens only after attempt 2 fails
[ ] No fourth attempt exists
[ ] Successful attempt stops retrying immediately
[ ] Three failures stop the entire operation
[ ] Orders are NOT fetched after authentication failure
[ ] Customers are NOT fetched after authentication failure
[ ] Products are NOT fetched after authentication failure
[ ] Existing sync data is NOT partially fetched/stored after authentication failure
[ ] Error clearly tells the user to verify integration email/password
[ ] Error instructs user to update Integration settings and Try Again
[ ] Connection endpoint follows the requested flow
[ ] Sync endpoint follows the requested flow
[ ] Sync Now creates connection then synchronizes
[ ] Promo Code capability is detected
[ ] store_capabilities.has_promo_code is updated
[ ] Capability update is tenant isolated
[ ] Existing synchronization remains unchanged
[ ] Existing tenant isolation remains unchanged
[ ] No e-commerce JWT persistence was added
[ ] No refresh-token architecture was added
[ ] No unrelated features were added
[ ] Existing tests pass
[ ] New tests pass
```

---

# 34. STRICT STOP CONDITION

When all acceptance criteria are satisfied:

**STOP.**

Do not continue implementing improvements.

If you discover any additional issue, write it only under:

```text
Potential Future Work
```

Do not modify code for it.

---

# FINAL REQUIRED IMPLEMENTATION

The only new behavior beyond the previously defined flow is:

```text
                    AI Commerce JWT
                           │
                           ▼
                     Decode JWT
                           │
               ┌───────────┴───────────┐
               ▼                       ▼
         Admin Email            Admin Password
               │                       │
               └───────────┬───────────┘
                           ▼
                  E-commerce Login
                           │
                    ┌──────┴──────┐
                    │             │
                  FAIL          SUCCESS
                    │             │
              Retry #2            ▼
                    │         Continue
                  FAIL
                    │
              Retry #3
                    │
              ┌─────┴─────┐
              │           │
            FAIL        SUCCESS
              │           │
              ▼           ▼
            STOP       Continue
              │
              ▼
      Return authentication
            error
              │
              ▼
       DO NOT FETCH DATA
              │
              ▼
 Admin updates Integration
 credentials in Admin Panel
              │
              ▼
           Try Again
```

**Implement exactly this. Nothing more.**
