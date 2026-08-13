# Widget Conversation Refinement — Audit (Phase 1)

Date: 2026-08-13 · Commit audited: `42c3539` (pre-refinement `b7d3e48` baseline) · Service: `aicommerce-ai-service-production` (Railway) · Store: `3ad1b6e1-e815-4592-aa74-e9692f2f8d36`

Scope: the widget chat surface (`/api/v1/widget/*`) and the conversation/agent pipeline it exercises. Baseline matrix: `docs/WIDGET_BASELINE_TEST_MATRIX.md`.

## Current flow (as found)

1. Widget bootstrap (`/api/v1/widget/bootstrap`) validates `X-Widget-Key` + `Origin`, issues a scoped session token (`rag:chat`, `recommendations:read`).
2. `/api/v1/widget/chat` runs **plain RAG orchestration**: retrieval (`RetrieverService.search`, tenant-scoped filters, hybrid config) → context message (business summary + chunk snippets) → LLM (single call, coordinator-style developer prompt).
3. `/api/v1/widget/recommendations` runs `RecommendationService.recommend` against the product catalog.
4. Confidence: `0.2 + 0.8 * avg(chunk score)`; escalation gated on `customer_id` presence + confidence < 0.3 (widget sends `customer_id=null`).
5. Conversations: `ConversationService` stores by `conversation_id` field; widget chat persists interactions and (after refinement) structured context.

## Broken flow (as found)

1. **Greetings / human / ticket / order / escalation intents all fell through to the same canned refusal** ("I don't have enough information to answer that.") — no intent routing, no sub-agents, no escalation path from the widget.
2. **Prompt-injection and out-of-scope messages were answered by the LLM** with RAG context — no gate, no cheap rejection.
3. **Escalation never triggered**: required `customer_id` (always null from the widget) AND a confidence gate that was never met.
4. **Document chunks invisible to retrieval**: 57 knowledge-document points in `kb_3ad1b6e1-…` lack `organization_id` in Qdrant payload → the org `eq` filter excluded the store's own KB; only the business summary carried store content.
5. **Recommendation sub-agent returned zero products** for this store: candidate vector search found products, but `filter_inventory`/`apply_budget_filter` require a Mongo catalog record (`find_by_id`) that does not exist for this store (products live as knowledge chunks) → everything filtered out, misleading "No products matched your criteria" / "Here are the best matches" fallback text.
6. **Conversation id edge**: a `conversation_id` that does not exist caused `save_interaction`'s `upsert=True` to violate the Mongo `$jsonSchema` validator (missing `customer_id`/`status`/`created_at`) → 500 instead of a clean 404/auto-create.

## Correct existing components

- Tenant-scoped retrieval (`RetrievalFilters(organization_id, store_id, …)`), dedup, chunk references.
- Business summary lookup and version stamping (`business_summary_version`).
- Widget bootstrap key/origin validation, scoped tokens, policy clamping (`apply_widget_policy`, plan-based).
- Conversation storage with tenant-scoped reads and history.
- Quota enforcement (`QuotaEnforcer`), runtime usage logging.
- Recommendation/bundle/sales/escalation sub-agents exist in the coordinator graph and serialize correctly (`_serialize_sub_agent_result`).

## Duplicate logic

- Widget chat duplicated the coordinator's job: hand-built developer prompt + single LLM call instead of using the existing `ConversationWorkflow`/coordinator routing. Refinement replaced this with the shared workflow (no new agent/RAG layer created).
- Widget-specific canned replies duplicated generic refusal text; refinement centralized them in `conversation_gate.py` and `widget_policy.py`.

## Missing context

- No structured conversation context (last recommendation, active entities) persisted or reused — every turn was stateless. Added `context` field via `_persist_chat_context` (`last_recommendation`, `last_bundle`, `last_ticket`, `last_escalation`), resolved by the contextual follow-up gate.
- Widget never sent/threaded `conversation_id` — added (`widget.js` + request schema).

## Security weaknesses (as found)

- No prompt-injection / unsafe-request / out-of-scope gate before LLM execution (injection reached the RAG prompt).
- No weapons/explosives/terrorism patterns (incl. Arabic) in any filter.
- Escalation/ticket responses could surface internal details (`store_id=`, `ticket_id=`, `assigned_to`, `priority`) when sub-agents ran; no sanitizer.
- Canned/meta answers were not distinct from LLM answers (`type` absent), so UI could not distinguish cheap vs LLM responses.

## Response-format weaknesses (as found)

- Single `response: str` contract: no structured products/product detail/bundle blocks, no `type` discriminator.
- Follow-ups ("show me them", "the second one", "cheapest") were re-answered from scratch by the LLM.
- No mechanism to render product cards in the widget; no `conversation_id` echo to thread turns.

## Refinement outcome (summary)

Implemented (see `docs/WIDGET_CONVERSATION_REFINEMENT_REPORT.md` for per-feature status): deterministic conversation gate (greeting/injection/unsafe/out-of-scope/follow-up classification), structured context model + follow-up resolver, sanitizer + escalation guard, additive response contract (`type`/`products`/`product`/`bundle`/`reference`), widget.js rendering, conversation threading, catalog-absent payload fallback for sub-agents, conversation-id 500 fix. No tenant-architecture, auth-contract, or API-contract changes were required.