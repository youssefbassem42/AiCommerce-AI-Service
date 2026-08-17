# Phase 3 Implementation Report — Escalation & Ticket Integrity Remediation

## 1. Summary

Domain 3 remediated three production-grade defects in the customer-service escalation pipeline:

- **B11** — MongoDB error 66 ("immutable field `_id` was found to have been altered") on every
  `BaseMongoRepository.update()` / `bulk_update()` because the replacement document regenerated a
  fresh `_id` on `from_entity()`.
- **B10** — false "handing over" claims to customers when ticket persistence failed (the support
  agent swallowed the exception and the response builder could not distinguish a durable handoff
  from a failed one).
- **B9** — duplicate tickets: the coordinator serializer dropped `ticket_id`, so the workflow's
  `already_escalated` guard never fired and re-evaluated the turn, creating a second ticket through
  the escalation agent.

Verdict: **PASS** — all fixes are in place, live-verified against the Atlas production database,
and covered by 20 new regression tests. Zero escalation-policy changes, zero new LLM inference
calls, zero new embedding calls, no provider changes, no OpenAI.

## 2. Root Cause

### B11 — immutable `_id` in replacement documents
`BaseMongoRepository.update()` performed
`replace_one({"_id": ObjectId(entity.id)}, doc.to_mongo_dict(), upsert=True)`.
`BaseMongoDocument.to_mongo_dict()` unconditionally writes `data["_id"] = ObjectId(self.id)`, and
`TicketAnalysisDocument.from_entity()` never maps `entity.id` onto the document, so a fresh ObjectId
was generated per call. MongoDB rejects a replacement that alters `_id` (error 66) when a document
matches, and rotates the identity on upsert. The repository layer already documented this invariant
for PlanPolicy/Analytics upserts (`test_nonid_upsert_replaces.py`); the generic `update()` path was
never covered.

### B10 — swallowed persistence failure, false handoff
`escalate_if_needed_node` logged `Ticket creation failed` and continued with `ticket_id = None`.
`generate_response_node` then emitted "I'm handing this over to our support team…" whenever
`escalation_needed` was set — regardless of whether a ticket existed. The escalation agent's
`notify_human_node` similarly returned an error dict but the graph continued through
`notify_customer_node`/`format_escalation_response_node`, and the formatter emitted a
notification_message claiming the escalation.

### B9 — `ticket_id` dropped in propagation, re-escalation
`execute_sub_agent_node` (`coordinator/nodes.py`) serialized only booleans
(`ticket_created`, `escalation_needed`) and never propagated `ticket_id` to the response. The
workflow's `already_escalated` guard reads `response["escalation_needed"]` / `response["ticket_id"]`
and `data["…"]`, but the coordinator puts its snapshot in `response["result"]` and never sets
`data`. Result: `already_escalated` stayed `False`, the decision engine re-fired, and the escalation
agent created a second ticket. Additionally, `create_ticket` had no idempotency: no
`conversation_id` was persisted, no reuse, no race protection.

## 3. Fixes

### 3.1 B11 — identity is the filter, never the replacement (base repo)
`app/infrastructure/mongodb/repositories/base_repository.py`:
- `update()` and `bulk_update()` now `pop("_id", None)` from the replacement document before
  `replace_one` / `ReplaceOne`.
- `create()`/`bulk_insert()` untouched (fresh `_id` on insert is correct).
- Fixes every entity updated through the generic repository (tickets, plans, insights, …), not just
  tickets.

### 3.2 Idempotent ticket creation (conversation-scoped)
- `TicketAnalysis` entity and `TicketAnalysisDocument` carry `conversation_id: str | None` (internal
  only — not exposed on `TicketDTO`, the API contract is unchanged).
- `TicketRepository.find_open_by_conversation(store_id, conversation_id)` added to the interface and
  the Mongo implementation.
- `TicketService.create_ticket()`:
  - reuses an existing OPEN ticket for the same `(store_id, conversation_id)` before doing any work
    (no sentiment analysis, no second ticket);
  - persists `conversation_id` on the entity;
  - on `ConcurrencyException` (duplicate-key race, mapped from MongoDB E11000) re-queries and reuses
    the winning ticket; re-raises only if no ticket can be found.
- `ensure_ticket_idempotency_index()` (new, idempotent, safe at startup): partial **unique** index
  `(store_id, conversation_id)` filtered to `conversation_id: {$type: string}` and
  `status: {$in: ["open", "in_progress"]}`. Wired into `main.py` lifespan. Partial filter uses `$in`
  because `$nin` is not supported in partial filter expressions (caught live on Atlas during
  deployment of the fix). Pre-existing documents without `conversation_id` are exempt, so no
  backfill or migration is required.

### 3.3 B10 — truthful escalation (support agent)
`app/agents/support/nodes.py`:
- `escalate_if_needed_node` returns `persistence_success: bool` on every path; on ticket creation
  failure it returns `ticket_id=None`, `error=…`, `persistence_success=False` and **skips the
  escalation agent entirely** (no blind retry).
- `generate_response_node`: the handoff message is emitted **only** when `persistence_success` is
  True; otherwise an honest fallback ("I'd like to have a specialist follow up… trouble submitting
  the request… try again or contact support") is used.

### 3.4 B10 — truthful escalation (escalation agent)
- `EscalationResponse.persistence_success: bool = False` added (backward compatible default).
- `notify_human_node` returns `persistence_success` True/False (and `False` when no ticket service is
  wired).
- `notify_customer_node` skips creating a notification record when the escalation was not persisted.
- `format_escalation_response_node` strips `ticket_id` and `notification_message` from the response
  when `persistence_success` is False — the customer-facing claim can never be emitted without a
  durable ticket.

### 3.5 B9 — propagate, then trust the propagation (coordinator + workflow)
`app/agents/coordinator/nodes.py`:
- `_serialize_sub_agent_result` now includes `ticket_id`, `escalation_reason`, `priority`,
  `assigned_to`, `eta`, `persistence_success`, `error` alongside the existing booleans.
- `execute_sub_agent_node` hoists `escalation_needed`, `ticket_id`, `escalation_reason`, `error`,
  `persistence_success` to the response **top level** so the workflow's existing
  `already_escalated` contract works.

`app/workflows/conversation/graph.py` (`evaluate_escalation_node`):
- `already_escalated` now also reads `response["result"]` (the coordinator snapshot) in addition to
  top-level and `data`.
- already-escalated branch: `should_escalate=True` only when the escalation is durable
  (`persistence_success`; legacy fallback `ticket_id` implies durable). A non-durable attempt yields
  `should_escalate=False`, `ticket_id=None`, keeps the sub-agent's honest reply, and records
  `source="sub_agent_unpersisted"` in the trace — never claims a transfer.
- decision-engine branch: the handoff content is written only when
  `result.persistence_success and not result.error`; otherwise the decision is downgraded and the
  AI's honest answer is kept.

## 4. Files Changed

| File | Change |
|---|---|
| `app/infrastructure/mongodb/repositories/base_repository.py` | B11: strip `_id` in `update()`/`bulk_update()` |
| `app/domain/ticket/entities/ticket_analysis.py` | `conversation_id` field |
| `app/infrastructure/mongodb/documents/ticket_document.py` | `conversation_id` field + mapping |
| `app/domain/ticket/repositories/ticket_repository.py` | `find_open_by_conversation` (interface) |
| `app/infrastructure/mongodb/repositories/ticket_repository.py` | `find_open_by_conversation` (Mongo) |
| `app/application/ticket/services/ticket_service.py` | idempotent `create_ticket`, `_enrich`, `_find_open_for_conversation`, race fallback |
| `app/infrastructure/mongodb/indexes.py` | `ensure_ticket_idempotency_index` (partial unique) |
| `app/infrastructure/mongodb/__init__.py` | export new index function |
| `app/main.py` | startup reconciliation of the idempotency index |
| `app/agents/support/nodes.py` | `persistence_success`, honest failure, no blind retry, honest fallback text |
| `app/application/ticket/dto/escalation_dto.py` | `EscalationResponse.persistence_success` |
| `app/agents/escalation/nodes.py` | honest `notify_human_node`, skipped customer notification, stripped claims |
| `app/agents/coordinator/nodes.py` | serializer + top-level escalation propagation |
| `app/workflows/conversation/graph.py` | `already_escalated` from result dict, durability gating |
| `tests/unit/application/test_escalation_integrity.py` | **new** — 20 regression tests |
| `tests/unit/application/test_ticket_service{,_extensions,_bugs}.py` | fixture: `find_open_by_conversation` |
| `tests/unit/workflows/test_conversation_workflow.py` | escalation-agent mocks model the response contract |
| `tests/unit/agents/test_support_honest_message.py` | handoff test now asserts durability contract |
| `tests/e2e/test_full_integration_chain.py` | fixture: `find_open_by_conversation` |

## 5. Escalation-Policy Audit (unchanged by design)

The deterministic decision engine (`evaluate_escalation`, signals, `CATEGORY_PRIORITY` p1–p4),
`REFUND_ESCALATION_THRESHOLD`, the widget escalation branch, `TicketCreateDTO`, `TicketDTO`, and the
Ticket API contracts were **not** modified. The mission's hard constraint "no escalation policy
change" is honored.

## 6. Verification

### 6.1 Test baselines
- Unit: **1927 passed** (was 1907; +20 new integrity tests, 0 deleted).
- Integration + e2e: **145 passed**.
- `ruff check` clean; `ruff format --check` clean on 883 files.
- CI (GitHub Actions, `cd ai-service && ruff check && ruff format --check`) will be green.

### 6.2 Live Atlas verification (production cluster)
1. `ensure_ticket_idempotency_index` created on `ai_commerce.ticket_analysis`:
   `store_id_1_conversation_id_1`, unique, partial `{conversation_id: {$type: "string"},
   status: {$in: ["open", "in_progress"]}}`. First attempt with `$nin` was rejected by the server
   (code 67) — caught before deployment, fixed to `$in`.
2. Real repository round-trip on Atlas: `create → update (priority change) → find_by_ticket_id` —
   **update no longer raises error 66**, `_id` preserved, `conversation_id` persisted.
3. Duplicate create for the same `(store_id, conversation_id)` was **rejected** with E11000 and
   mapped to `ConcurrencyException` — the race-protection path the service converts into a reuse.
4. Probe documents cleaned up afterwards.

### 6.3 No new external calls
The fix adds zero LLM inference calls (the support failure path actually **skips** the escalation
agent), zero embedding calls, and no new provider/network dependencies. The only new network effect
is one idempotency index at startup (no-op on subsequent boots) and a cheap index-backed
`find_open_by_conversation` lookup before ticket creation.

## 7. Architecture & Integration Safety Audit

- **Base repo:** `_id` stripping is the smallest responsible layer; `create` semantics unchanged;
  existing upsert invariants (`test_nonid_upsert_replaces.py`) still hold.
- **Ticket flow:** reuse happens before sentiment analysis (no wasted LLM-adjacent work on
  duplicates); the RAG service's `_check_escalation` and the widget path are untouched and benefit
  automatically from idempotent creation.
- **Workflow honesty:** all three paths that could claim a handoff (already-escalated, decision
  engine, escalation-agent error) now require durability before emitting transfer language.
- **Backward compatibility:** new fields are optional/defaulted; `TicketDTO` unchanged; no DB
  migration; the partial unique index cannot reject pre-existing documents.

## 8. Known Limitations / Deferred Findings

- `TicketService.update_status` still resolves tickets via `find_by_id` (uuid4) and can 404; this is
  outside the B9/B10/B11 scope and is deferred (documented, not fixed).
- `ticket_analysis` JSON-schema validator (`setup_collection_validators`) is still not invoked at
  startup; the p1–p4 vs low/medium/high/urgent priority mismatch is therefore latent. Documented,
  not changed (validator install + priority normalization would be a policy change).
- `find_open_by_customer` (customer-scoped dedupe) remains in place alongside the conversation-scoped
  key; both are cheap index-backed reads.
- Live SBG gateway behavior not probed (no local key; budget constraint unchanged).

## 9. Verdict

**PASS.** B11, B10, and B9 are fixed at their root layers, verified against the live production
database, covered by 20 regression tests, and constrained to the smallest safe change set with zero
policy changes and zero new inference/embedding calls.
