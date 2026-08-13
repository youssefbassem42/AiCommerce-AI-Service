# Widget Agent Integration — Final Report

Date: 2026-08-13
Status: implementation complete, pending deployment + live re-test

## 1. What changed

`/api/v1/widget/chat` was rewired from the plain RAG path (`RagOrchestrationService`) to the
existing orchestration stack (`OrchestrationService → ConversationWorkflow → CoordinatorAgent
→ sub-agents`), with the store's knowledge injected as retrieval context. No new agents,
workflows, or RAG pipelines were created — the adapter reuses existing abstractions.

### New flow (app/api/widget/router.py `widget_chat`)
1. Ownership check (conversation belongs to store) — unchanged.
2. Plan + `WidgetServerPolicy` clamping — unchanged (retrieval controls still policy-bound).
3. Tenant-bound retrieval via `RetrieverService` (honors policy `top_k`/`score_threshold`/
   `use_hybrid`/`use_mmr`/`rerank`, tenant filters org+store+language+scope).
4. Business summary v{latest} loaded for the store.
5. If any chunks or a summary exist, a neutral system context message is prepended to the
   conversation history (reuses `CHUNK_HEADER`/`BUSINESS_SUMMARY_HEADER` builders). The
   context instructs grounded answers for knowledge questions but does not force refusals,
   so greetings/small-talk stay natural.
6. `orchestration_service.chat(user_input, store_id, customer_id=None, conversation_id,
   history, metadata={widget_id, session_id, path})` runs the coordinator workflow:
   - executable intents → dedicated agents (recommendation/bundle/sales/support/escalation),
   - general → generic e-commerce assistant LLM with injected context.
7. Interaction persisted via `ConversationService.save_interaction`; a fresh `conversation_id`
   is minted when the client does not send one (widget client persists it back).
8. Response mapping: `ChatResponse → WidgetChatResponseSchema`; citations extracted with the
   same `[citation:N]` rule as the RAG path; `chunk_references` from retrieval; confidence:
   `1.0` for agent-handled intents, otherwise `0.2+0.8·avg(score)` (0.3+0.7 with summary),
   `0.0` when ungrounded (client shows the low-confidence hint).

### Data fixes (see docs/KNOWLEDGE_TENANT_DATA_AUDIT.md)
- Legacy salla chunks reindexed with `organization_id` → org-scoped retrieval returns 97/97.
- Product vectors enriched with structured `price`/`currency`/`image_url`/`specs`; the
  recommendation agent now returns real prices without a budget mention.
- Chunking/sync pipelines stamp orgs at the source; `generate_chunks_task` resolves org
  best-effort from `entities` when callers don't have it.

## 2. Findings fixed by the mission

| Baseline behavior (before) | After (expected) |
|---|---|
| hello/talk-to-human/create-ticket → canned refusal | natural chat; human handoff via escalation agent; ticket creation via support agent |
| return-policy answered from summary only, 0 citations, hallucinated `[citation: Refund Policy]` | grounded in KB chunks (now retrievable), real citations |
| bundle → partial (no phone case) | full bundle via BundleAgent + enriched product vectors |
| order status → refusal | support/escalation agents with anonymous ticket flow |
| budget → "$30.00" from chunk text | structured price metadata |
| price without budget → USD 0 | structured price from payload |

## 3. Behavior deltas (accepted, documented)

- **Model policy:** orchestration uses the service default model/failover (same as
  `/api/v1/ai/chat`), not the widget plan's `fallback_model`. The widget plan still governs
  retrieval config and quota/rate limits.
- **Legacy fields:** `model`, `temperature`, `max_tokens`, `provider_name` remain accepted
  (clamped) but no longer reach the LLM — provider/model are server-controlled for
  orchestrated traffic.
- **Escalation:** anonymous ticket creation is supported (`customer_id=""`); verified via
  existing `escalate_if_needed_node`.

## 4. Deployed vs repo drift (audit finding)

The deployed `/api/v1/widget/chat` OpenAPI contract required a `provider_name` query param
that exists in **no** repo commit (deploy `9a53fb3c` of `b7d3e48`, Dockerfile
`/ai-service/Dockerfile`). The new handler accepts an optional (deprecated) `provider_name`
for client compatibility; a fresh deploy from the repo normalizes the contract.

## 5. Tests

- `tests/unit/modules/widget/test_widget_policy.py` updated to the new dependency contract
  (orchestration + retrieval + summary + conversation mocks); clamping assertions moved to
  the retrieval config.
- Full unit suite: **1462 passed**, lint clean.

## 6. Remaining before production

1. Deploy the backend (requires user approval — `railway` accept-deploy / push).
2. Re-run the 9-case matrix (`docs/WIDGET_BASELINE_TEST_MATRIX.md`) against the deployed
   app and update results.
3. Remove the temporary qdrant public domain `qdrant-production-4f7a.up.railway.app`
   (created only for debugging access).
