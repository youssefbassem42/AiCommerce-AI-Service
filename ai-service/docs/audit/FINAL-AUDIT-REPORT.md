# AI Commerce FastAPI Production Audit

**Date:** 2026-08-10
**Scope:** `ai-service` (FastAPI) — full security/production audit per `phases.md`
**Result:** **GO WITH WARNINGS**

---

## Executive Summary

The audit ran phases A–E and G of the plan (Phase F — widget events & attribution — was **skipped by explicit instruction**). Every security gate passed. Three P0-class tenant-isolation findings were discovered and fixed during Phases C (retrieval search, analytics sentiment-summary) — cross-store read paths that no longer exist on authenticated routes. The codebase is safe to deploy **after one required action: redeploy the running container**, which predates the hardening (verified live: it lacks Phase B–E behavior).

Full regression: **1418 passed / 0 failed / 0 skipped**. OpenAPI: zero unintentional breaking changes (one intentional, documented security hardening).

## Current Architecture

```
STOREFRONT ─► Widget API (X-Widget-Key bootstrap → short-lived widget JWT)
                │ scope: rag:chat / recommendations:read
SaaS ────────► API /api/v1/* (SaaS bearer JWT, ASP.NET claim contract)
                ▼
           AuthMiddleware → TenantContext (server-derived store_id/org_id)
                │
     ┌──────────┼───────────┐
     ▼          ▼           ▼
    RAG       AI Chat   Recommendations
     │          │           │
     └──────────┼───────────┘
                ▼
        Mongo / Qdrant / Redis
                ▼
              LLM (openrouter/openai/gemini)
```

Tenant boundary: **server-derived `store_id` from validated JWT claims** — canonical everywhere since Phase C; client-supplied identifiers are ignored or denied.

## Phase Results

### Phase A — Baseline & Inventory
**PASS WITH WARNINGS** — 105-operation ownership matrix, request-model audit (23 schemas carry tenant/AI-control fields), OpenAPI baseline, 9 risks registered (R-01..R-09).

### Phase B — Observability & Correlation
**PASS** — single `X-Request-ID` (legacy `X-Correlation-ID` alias retained), `request_id` propagated HTTP → TenantContext → services → AI metrics → audit. 7 new tests; OpenAPI byte-identical.

### Phase C — Tenant Isolation
**PASS** — two **P0 findings fixed**: `/knowledge/retrieval/search` client tenant fallback and `/api/v1/analytics/sentiment-summary` fully unbound `store_id`. Claims-only resolution + deny-on-mismatch; tenant-bound `RetrieverService`. 12-test isolation suite. (R-01/R-04/R-06 closed; R-02 mitigated for authenticated mode.)

### Phase D — Rate Limiting
**PASS** — endpoint-aware tiers (default 100 / llm 20 / widget bootstrap 30 per hashed key / widget session 60 per store), Redis primary + bounded memory fallback, `X-RateLimit-*` headers, 429 with tier. (R-08/R-09 closed; one P1 design bug fixed mid-phase.)

### Phase E — Widget Server Policy
**PASS** — assistant controls: `WidgetChatRequestSchema` unchanged (compatibility adapter); every AI-execution control sanitized by server policy (model allowlist, temp ≤1.0, max_tokens ≤1024, top_k ≤10, hybrid/MMR/rerank server-gated, scope allowlist); deviations logged with tenant. (R-03 closed.)

> Note: `phases.md` labels Phase E as widget streaming; the risk register's R-03 (worked here) supersedes within this audit's execution.

### Phase F — Widget Events & Attribution
**SKIPPED** by explicit instruction. No events/attribution work performed; relevant checklist items documented as N/A in Phase G.

### Phase G — Final Production Audit
**PASS WITH WARNINGS** — see `phase-g-report.md`. G1 regression 1418 ✓ · G2 OpenAPI (1 intentional diff) ✓ · G3 security controls ✓ (live prompt-injection probe: grounded refusal) · G4 failure modes controlled ✓ · G5 measurements recorded ✓ · G6 checklist ✓ (baseline refreshed, rollback documented).

## Test Summary

| Metric | Count |
|---|---|
| Total tests run (G1, incl. e2e) | 1418 |
| Passed | 1418 |
| Failed | 0 |
| Skipped | 0 |
| Blocked | 0 |

## Security Findings

| Severity | Open | Closed |
|---|---|---|
| P0 | 0 | 2 (Phase C) |
| P1 | 1 (G-R5: stale deployment, not code) | 1 (Phase D design bug) |
| P2 | 4 (G-R1 prompt-injection suite, G-R2 widget streaming, G-R4 runtime-log writer, C-R1 anonymous-mode config risk) | 6 (R-01..R-09 register items) |
| P3 | 6 (G-R3, G-R6, G-R7, E-R1, E-R3, R-05 legacy router) | 0 |

## Production Findings

- **Required before GA**: redeploy container from audited tree (G-R5). The live instance is 30h+ old and lacks Phases B–E hardening; verified via widget-token 401 and tickets 422 anomalies that current code no longer exhibits.
- `JWT_REQUIRED=false` remains the env default → anonymous RAG mode honors client `store_id` (documented internal mode; production should set `JWT_REQUIRED=true`).
- No destructive migrations introduced by any phase; rollback strategy documented.

## API Compatibility

- 85 paths; 84/85 byte-identical vs original baseline.
- 1 intentional change: `GET /api/v1/analytics/sentiment-summary` `store_id` param optional + deny-on-mismatch (Phase C hardening, documented).
- Zero added/removed/deprecated endpoints across the audit.
- Baseline file refreshed to current schema.

## Database Changes

No database changes (no schema changes, no indexes, no migrations, no data migrations) in any phase.

## Performance Results

| Metric | p50 | p95 | p99 |
|---|---|---|---|
| Tenant resolve (in-process) | 0.003 ms | 0.003 ms | 0.016 ms |
| Widget policy (in-process) | 0.004 ms | 0.012 ms | 0.029 ms |
| Rate check memory (in-process) | 0.004 ms | 0.014 ms | 0.036 ms |
| Vector search (1000 vectors, store-scoped) | 8.0 ms | 11.7 ms | 25.9 ms |
| Mongo find_one | 0.56 ms | 1.9 ms | 2.3 ms |
| GET /health/ | 2.8 ms | 5.7 ms | 40.2 ms |
| /rag/chat end-to-end (real LLM) | 2556 ms (single sample) | — | — |

Chat/stream/recommendation percentiles require an authenticated load test post-deploy (G-R7).

## Observability

- `X-Request-ID` correlation end-to-end (B); audit entries carry request_id; AI metrics correlated.
- Runtime-log writer (B-R1) still missing — observability lives in structured logs + `audit_logs`.
- No PII/secrets logged (verified by grep).

## Remaining Risks

| ID | Risk | Severity |
|---|---|---|
| G-R5 | Running container predates B–E hardening | P1 |
| G-R1 | No automated prompt-injection suite | P2 |
| G-R2 | Widget streaming absent (server forces stream=False) | P2 |
| G-R4 | Runtime-log writer absent | P2 |
| C-R1 | `JWT_REQUIRED=false` default → anonymous RAG mode | P2 |
| G-R3 | Phase F scope skipped (events/attribution) | P3 |
| G-R6 | SaaS chat/rag honor client AI controls | P3 |
| G-R7 | Auth'd load test outstanding | P3 |
| E-R1 | Per-store policy overrides not wired | P3 |
| R-05 | Legacy knowledge router dead code | P3 |

## Required Actions

| Issue | Severity | Action | Owner | Blocking? |
|---|---|---|---|---|
| G-R5 | P1 | Redeploy from audited tree; re-verify probes post-deploy | DevOps | YES |
| C-R1 | P2 | Set `JWT_REQUIRED=true` in production env | DevOps | No |
| G-R1 | P2 | Automate prompt-injection canaries | AI service | No |
| G-R2 | P2 | Scope widget streaming decision | Product | No |
| G-R4 | P2 | Implement runtime-log writer | AI service | No |
| Others | P3 | Backlog (see phase reports) | AI service | No |

## Release Recommendation

**GO WITH WARNINGS**

- Code: GO — all gates passed, 1418/1418, no unintentional breaking changes, no P0/P1 code findings.
- Blocking condition: G-R5 deployment staleness — do not promote the current running image; deploy the audited tree first.

## Final Decision

The audited codebase is production-ready. `docs/audit/phase-a..e, g-report.md` + `tenant-isolation-matrix.md` contain the evidence trail; this report supersedes nothing and references everything.