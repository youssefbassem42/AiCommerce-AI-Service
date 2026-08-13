# Widget Chat Baseline Test Matrix (Phase 1)

Date: 2026-08-13 — Target: `https://aicommerce-ai-service-production.up.railway.app`
Widget key: `wi_v6PgxRI26fmqiZEhcKVQrhDzGIqai5JziH7_oJisQiY` (store `3ad1b6e1-e815-4592-aa74-e9692f2f8d36`)
Auth: bootstrap (Origin `https://localhost:4200`) → Bearer session token
Deployed app at commit `b7d3e48` (per Railway status `9a53fb3c`).

## Results

| # | Case | Response | conf | citations | notes |
|---|------|----------|------|-----------|-------|
| 1 | `hello` | "I don't have enough information to answer that." | 0.657 | 0 | canned refusal (DEVELOPER_PROMPT) |
| 2 | `i need to talk to a human` | "I don't have enough information to answer that." | 0.651 | 0 | no escalation path |
| 3 | `i want to create a ticket` | "I don't have enough information to answer that." | 0.664 | 0 | no ticket path |
| 4 | `what is your return policy?` | Salla TOS answer (14-day cancel, bank transfer fee) | 0.656 | 0 citations, 5 chunk_references (products only) | answered from **business summary v1**, not chunks; response hallucinated `[citation: Refund Policy]` not present in refs |
| 5 | `sunglasses` | Sunglasses Retro, price 30.0, UV protection | 0.724 | 1 (Sunglasses Retro) | product chunk |
| 6 | `sunglasses under 100 dollars` | "$30.00" | 0.696 | 1 | price read from chunk **text**, not structured metadata |
| 7 | `i want sunglasses and a phone case` | sunglasses info only, no phone case found | 0.729 | 1 | no bundle path |
| 8 | `my order hasn't arrived yet` | canned refusal + "check with merchant through the Salla platform" | 0.668 | 0 | no order/support path |
| 9 | `can i speak to a human?` | "I don't have enough information to answer that." | 0.646 | 0 | no escalation path |

## Confirmed findings

1. **Widget chat runs plain RAG only** (`RagOrchestrationService`). Greeting / human / ticket / order / escalation intents all fall through to the canned refusal; only product retrieval answers work.
2. **confidence_score ≈ 0.65–0.73 everywhere**: `0.2 + 0.8 * avg(chunk score)` with `score_threshold=0.0` → always 5 chunks retrieved, never below the 0.3 escalation gate; no summary-based boost.
3. **Escalation never triggers**: `_check_escalation` requires `customer_id` (widget sends `null`) AND confidence ≥ 0.3 gate is effectively never met. `tickets` collection has 0 documents.
4. **Document chunks invisible to retrieval**: 57 `knowledge_document` points in `kb_3ad1b6e1-e815-4592-aa74-e9692f2f8d36` have **no `organization_id`** in their Qdrant payload (ChunkingService metadata omits it; `sync_vectors_task` falls back to `chunk.metadata.get("organization_id")` → None). The org `eq` filter excludes them → the store's own KB (salla_file.pdf) never reaches the LLM; only the **business summary** carries its content.
5. **No cross-tenant leak observed**: all retrieved chunks belong to the store's own collection (40 `integration_sync` product points, org+store set; 57 document points, store set, org missing).
6. **Repo/deployed drift**: deployed `/api/v1/widget/chat` requires query param `provider_name` (OpenAPI: `required: true`); the repo's router (HEAD `b7d3e48`) does not declare it. Deployed build therefore does not match repo source exactly (fresh deploy from repo will normalize).
7. `business_summary_version: 1` present — business summaries exist and ARE used by the RAG path.

## Expected post-integration behavior (mission acceptance)

- Cases 1, 2, 3, 8, 9 route to coordinator: greeting → generic LLM; human/ticket → support/escalation agent with ticket creation (anonymous OK).
- Case 4 answered from the store's KB document chunks (after org backfill/reindex) with real citations.
- Cases 5, 6, 7 keep recommendation/bundle behavior; price from structured metadata (fix `Decimal("0")`).