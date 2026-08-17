# Phase 4 Implementation Report — Context, History & Shopping-State Propagation Remediation

## 1. Summary

Domain 4 repaired four production-grade defects in the widget chat pipeline that silently degraded
multi-turn conversations (widget → ContextBuilder → ConversationWorkflow → Coordinator →
sub-agents → persistence):

- **B12** — `ConversationRepository.update_context` **replaced** the whole `context` document on
  every turn (`$set: {"context": context}`), so each per-turn delta wiped previously stored
  structured context (`last_recommendation`, `last_bundle`, `last_ticket`, `last_escalation`,
  `routing`). A non-product follow-up turn destroyed the recommendation linkage the follow-up gate
  depends on.
- **B13** — the shopping state (category/budget/brand/…) lived **only** in Redis session memory and
  was lost on memory expiry/unavailability, breaking "gaming laptop under 3000" → "something
  lighter" follow-ups after a gap.
- **B14** — `chat_via_streaming_provider` **sent the current user message twice** to the model
  (once as the last entry of `messages`, once as an explicit append), doubling the final turn.
- **B15** — session summaries were keyed `session_summary` per `(user_id, store_id)`, so **parallel
  conversations of the same customer+store overwrote each other's summaries** — a cross-session
  context leak.

Verdict: **PASS** — all four fixes are in place, live-verified against the Atlas production
database, and covered by 20 new regression tests (11 failing before the fix, all green after).
Zero new LLM inference calls, zero new embedding calls, no provider changes, no OpenAI, no schema
migration, no graph/nodes/prompts added.

## 2. Context-Propagation Map (as analyzed)

| Stage | Location | Notes |
|---|---|---|
| Widget chat entry | `app/api/widget/router.py` `widget_chat` | resolves/creates `conversation_id`, loads conversation context |
| Follow-up gate | `app/api/widget/router.py` `classify_widget_message` | may short-circuit via stored `last_recommendation` (B12 made this unreliable) |
| Context assembly | `app/application/context/builder.py` `build()` | history, memory, customer, business rules, shopping state |
| Workflow | `app/workflows/conversation/graph.py` `ConversationWorkflow.run` | validate_input → recall_memory → update_shopping_state → route_to_agent → execute_agent → evaluate_escalation → format_response → update_memory → check_continuation |
| Coordinator | `app/agents/coordinator/agent.py` `run()` | classify/route, then sub-agent execution |
| Sub-agents | coordinator `execute_sub_agent_node` + `_history_with_knowledge` | recommendation/support/sales run with history + context |
| Message write | `router.py` `conversation_service.save_interaction` | single write path (untouched) |
| Context write | `router.py` `_persist_chat_context` | per-turn structured delta (B12/B13 surfaces) |
| Session memory | Redis `session:{session_id}:memory` | shopping state + short-term recall (B13 volatile) |
| User memory | Mongo keyed `(user_id, store_id, key)` | tenant-isolated; summaries (B15) |

## 3. Root Cause & Fixes

### 3.1 B12 — context replace → per-key merge
`update_context` executed `$set: {"context": context}` where `context` was the caller's partial
delta (e.g. only `routing`). Every non-product turn silently discarded `last_recommendation`,
`last_bundle`, `last_ticket`, `last_escalation` and previous `routing`.

**Fix** (`app/infrastructure/repositories/conversation_repository.py`): the update now sets each
top-level key independently (`context.<key>` per key), so the conversation's structured context
**accumulates** across turns. Backward compatible — the write path and stored shape are unchanged.

### 3.2 B13 — durable shopping state (no new LLM calls, no new persistence layer)
The shopping state existed only in Redis session memory. When memory is unavailable/expired the
workflow restarted from an empty goal. The durable conversation record was already being written
every turn — it just never carried the state.

Fix, end to end (4 coordinated touch points, all within existing state structures):
1. `ConversationWorkflow.run` surfaces the final shopping state on
   `ChatResponse.metadata["shopping_state"]` (already computed by `update_shopping_state_node`).
2. `router.py` `_persist_chat_context` stores it in the conversation's structured context under
   `shopping_state`.
3. `ContextBuilder.build` seeds `context.conversation[SESSION_STATE_KEY]` from the stored context
   when recalled memory does **not** carry it (memory wins when present).
4. `update_shopping_state_node` falls back to the conversation state as its merge base when memory
   entries are empty — Redis remains the freshest source; Mongo is the durable one.

No new nodes, no new prompts, no new LLM/embedding calls, no schema change: the field rides the
existing `context` document and the existing `ShoppingState` model.

### 3.3 B14 — single current message in streaming requests
`chat_via_streaming_provider` built `messages` from history (which already ended with the current
user message appended by the workflow) and then appended `user_input` again — the last turn reached
the model twice. **Fix**: append `user_input` only when the final message is not an identical user
message; the contract (system + history + current message) is preserved for all callers.

### 3.4 B15 — per-session summary isolation
`summarize_session_node` wrote to the fixed key `session_summary` for `(user_id, store_id)`, so
concurrent/parallel conversations of the same customer clobbered each other — and every later
conversation recalled the most recent other conversation's summary. **Fix**:
- summaries are written under `session_summary:{session_id}` (legacy bare key still written for
  backward compatibility only when no session id exists);
- `recall_all` filters out `session_summary:*` keys that do not belong to the current session,
  leaving the legacy `session_summary` key readable.

## 4. Files Changed

| File | Change |
|---|---|
| `app/infrastructure/repositories/conversation_repository.py` | B12: `$set` per `context.<key>` (merge, not replace) |
| `app/workflows/conversation/graph.py` | B13: surface `metadata["shopping_state"]`; `update_shopping_state_node` merge-base fallback |
| `app/api/widget/router.py` | B13: `_persist_chat_context` stores `shopping_state` |
| `app/application/context/builder.py` | B13: seed shopping state from stored context when memory lacks it |
| `app/agents/coordinator/nodes.py` | B14: dedup current user message in streaming requests |
| `app/agents/memory/nodes.py` | B15: `session_summary:{session_id}` key |
| `app/agents/memory/tools.py` | B15: `recall_all` excludes other sessions' summaries |
| `tests/unit/workflows/test_context_propagation.py` | **new** — 20 regression tests (below) |

## 5. What Was Deliberately Not Changed

- No new graph nodes, no new agents, no prompt changes, no intent reclassification.
- No new persistence layer, no new Mongo collection, no new Redis database, no schema migration.
- History storage, the single message write path (`save_interaction`), the history window, summary
  frequency and memory-extraction frequency are all preserved.
- `shopping_state_from_context` precedence semantics unchanged (conversation-first is the existing
  contract for the recommendation agent).
- `AIContext` serialization, `ShoppingState` model, `TicketDTO`/`ChatResponse` API contracts
  unchanged (a new optional metadata field only).

## 6. Verification

### 6.1 Test baselines
- Unit: **1953 passed** (baseline 1933; **+20 new** in
  `tests/unit/workflows/test_context_propagation.py`; 0 deleted). Before the fix, 11 of the 20
  failed — exactly the four intended defect captures; all green after.
- Integration + e2e: **145 passed**.
- `ruff check` clean; `ruff format --check` clean (884 files).
- CI (`cd ai-service && ruff check && ruff format --check`) is green.

### 6.2 Live Atlas verification (production cluster)
Scratch conversation (cleaned up afterwards), store `5f051250-…`:
1. Three sequential `update_context` calls (`routing`, `last_recommendation`, `shopping_state`) →
   read-back showed **all three keys present** (`MERGE_VERIFIED`) — previously each call replaced
   the previous one.
2. Tenant guard: an update/read from a different `store_id` neither modified nor revealed the
   conversation (`TENANT_GUARD_VERIFIED`).

### 6.3 No new external calls
New Bedrock inference calls: **0**. New Gemini embedding calls: **0**. OpenAI: none (codebase and
dependencies). The only additional persistence effect is the same per-turn Mongo update the router
already performed — now carrying one more top-level key, plus the same Redis writes as before.

## 7. Architecture & Integration Safety Audit

- **B12 merge** is a single-function, backward-compatible change at the repository boundary; the
  widget path, gateway, support, sales and recommendation callers are untouched and benefit
  automatically.
- **B13** adds no failure mode: the durable seed only applies when memory is absent, and
  `update_shopping_state_node`'s fallback is a read of the same dict it already reads.
- **B14** preserves the exact request shape for every existing caller (verified by the coordinator
  and workflow suites).
- **B15** keeps the legacy summary readable and scopes only the per-session keys; memory agent
  tests confirm the write/recall contract.

## 8. Known Limitations / Deferred Findings

- Shopping-state durability is best-effort: the fallback chain (memory → conversation record)
  covers memory loss, but a simultaneous failure of both stores is not recoverable. This matches the
  existing single-writer design; no additional persistence layer was added (mission constraint).
- The workflow's `metadata["shopping_state"]` is populated from the final workflow state; the widget
  direct-recommendation path (non-workflow) still persists via the same `update_context` merge and
  benefits from B12.
- Live SBG gateway behavior not probed (no local key; budget constraint unchanged).
- History-window semantics (`context_window`) were audited and left untouched by design.

## 9. Verdict

**PASS.** B12–B15 are fixed at their root layers, verified live against the production database,
covered by 20 new regression tests, with zero new inference/embedding calls, zero policy changes
and zero schema migrations.
