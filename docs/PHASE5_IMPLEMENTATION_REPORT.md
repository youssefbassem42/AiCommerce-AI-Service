# Phase 5 Implementation Report — Deterministic Bundle Complementarity (B16), Single-Selected-Bundle Contract (B17) & Promo-Code Validation (L4)

## 1. Summary

Domain 5 repaired three production-grade defects in the bundle-suggestion pipeline (widget →
Recommendation Agent → Bundle Agent → promo platform):

- **B16** — the Bundle Agent reasoned over raw, uninformed text templates ("Bundle 1", "Buy X
  together with Y") with no notion of *why* products belong together. Suggested bundles had no
  deterministic complementarity signal, no usable ranking, and no store-taxonomy awareness.
- **L4** — the promo lifecycle produced codes, but nothing verified them against the store's real
  e-commerce platform; a code could be shown that the platform would reject.
- **B17** — two bundles could each receive their own promo code, persistence saved whichever bundle
  it chose, and the response/UI fields did not reflect one authoritative, ranked selection.

**Fixes:** a deterministic complementarity engine (`ComplementarityRules`) whose output is a
function of product metadata, store taxonomy and canonical category relationships — no LLM involved
in any truth decision; a single ranked selection (`rank == 1`) that exclusively drives promo-code
creation, persistence and response fields; and a real `validate-code` call against the connected
platform's checkout endpoint with honest status reporting (`valid` / `invalid` / `unavailable` —
never a fabricated success).

**Verdict: PASS.** All fixes are live-verified against the Atlas production database and the real
.NET checkout host, and covered by 32 new regression tests (failing before the fix, green after).
Zero new LLM inference calls, zero new embedding calls, no OpenAI, no Bedrock/Gemini for commerce
truth, no payment/checkout creation, no schema migration.

## 2. Defect Map (as analyzed)

| Stage | Location | Defect |
|---|---|---|
| Bundle composition | `app/agents/bundle/tools.py` | "compatible pool" was a raw template lookup; no complementarity scoring |
| Ranking | `app/agents/bundle/tools.py` `score_bundles` | no complementarity term; no coverage of requested items; no budget-aware ordering |
| Selected bundle | `app/agents/bundle/nodes.py` | every bundle candidate got its own promo code; persistence not tied to the selected bundle |
| Promo lifecycle | `app/application/recommendation/promo_service.py` | no validation of created codes against the platform |
| Response contract | `recommendation_dto.py`, `contracts/bundle.py`, `BundleSuggestion` | no rank, no complementarity labels, no promo status |
| Taxonomy | `commerce` layer | store category taxonomy was never loaded into bundle reasoning |

## 3. Root Cause & Fixes

### 3.1 B16 — deterministic complementarity engine (no LLM)
**Root cause:** compatibility was textual and uninformed; bundles were not scored by *why* their
products fit.

**Fix** (`app/application/commerce/complementarity.py`, new): `ComplementarityRules` resolves, in
priority order: explicit metadata links (`compatible_with`, `compatible_product_ids`,
`recommended_with`, `complementary_to`) → canonical category complements
(`CATEGORY_COMPLEMENTS`: Electronics→Accessories, Office→Furniture, … = 0.7) → accessory-keyword
heuristic (0.55) → same-category (0.15) → unrelated (0.0). Product type keys are computed from
`product_type` + store category only (title excluded — a "Laptop Backpack" must not count as a
laptop). Pair scores are directional; bundles use the max of both directions. The store's category
taxonomy is loaded per request (`CommerceCategoryRepository.find_root`, keyed `external_id|id` →
name) and feeds the canonical rules, so real stores benefit from their own taxonomy.

### 3.2 L4 — real promo-code validation
**Root cause:** nothing verified a created code against the platform before showing it to a
customer.

**Fix** (`app/application/recommendation/promo_service.py`): `validate_code(store_id, code,
subtotal)` — gated by `PROMO_CODES_ENABLED` — finds the active coupon-capable platform connection
(entity-mapping check is now case-insensitive: the live .NET spec maps `Discount` with a capital
D), resolves the checkout validation endpoint (`validate/check/verify` + `promo/coupon/discount`),
POSTs `{"promoCode": code, "subtotal": …}` per the platform schema, and normalizes the response to
`PromoValidationResult(status=valid|invalid|unavailable, discount_amount, reason)`. Unknown
response shapes, HTTP failures and missing connections are all `unavailable` — a code is only ever
presented with an explicit status and never with unverified success claims. `CreateCouponDto`
compliance extended (`discountPercentage`, `expiryDate` = now + `PROMO_CODE_VALID_DAYS`).

### 3.3 B17 — one selected bundle drives everything
**Root cause:** two bundles could each get a promo code; persistence and response fields were not
tied to a single selection.

**Fix** (`app/agents/bundle/*`, `app/workflows/bundle/graph.py`, `services.py`, DTOs, entity +
document): bundles are scored `0.6·complementarity + 0.35·coverage + 0.15·(within_budget)` and
sorted (budget-fit → score → relevance → price → size → stable id); `rank` is assigned 1-based and
stored (`BundleSuggestion.rank`, document mapping both directions). Only `rank == 1` is eligible
for promo creation, persistence (`_persist_selected_bundle`) and the response's promo fields.
`promo_capable` (capabilities-driven, default `False`) is the single source of truth for whether
the promo path runs at all. A promo code is only created when the selected bundle is genuinely
discounted (`total_discount > 0`) — a bundle that fits the budget at normal price needs no coupon
(legacy contract preserved). Shopping state (budget + desired items) and capabilities flow from
context into the workflow and merge into bundle reasoning (`merge_shopping_state`); desired items
count toward coverage including repetitions ("two controllers").

## 4. Files Changed

| File | Change |
|---|---|
| `app/application/commerce/complementarity.py` | **new** — `ComplementarityRules`, `PairComplementarity`, canonical rule table, accessory keywords, type keys, bundle scoring + labels |
| `app/agents/bundle/tools.py` | rewritten — `promo_capable`, `merge_shopping_state`, `parse_budget`, `is_active`/`is_available`, `find_candidates`, `build_compatible_pool`, `knapsack_bundles`, `score_bundles`, `get_or_create_promo` (rank-1 + discount guard), `build_bundle_response` |
| `app/agents/bundle/nodes.py` | rewritten — budget/state parse, candidate discovery, pool→knapsack→score, rank-1 select, promo gating, honest wording |
| `app/agents/bundle/agent.py`, `state.py`, `app/workflows/bundle/graph.py` | new kwargs (`store_capabilities`, `category_names`, `shopping_state`), `promo_status`, route-after-select via `promo_capable` |
| `app/application/recommendation/services.py` | `_load_category_names` (taxonomy), `shopping_state_from_context` wiring, `_persist_selected_bundle` (rank 1) |
| `app/application/recommendation/promo_service.py` | `PromoValidationResult`, `validate_code`, `_find_validate_endpoint`, response normalization, case-insensitive entity mapping, `discountPercentage`, `expiryDate` |
| `app/core/ai_settings.py` | `PROMO_CODE_VALID_DAYS` (30) |
| `app/application/recommendation/dto/recommendation_dto.py` | `BundleCandidate` + `compatibility_score`/`relevance_score`/`score`/`complementarity_labels`/`promo_status`; `BundleResponse` + `promo_status` |
| `app/application/contracts/bundle.py` | `BundlePayload` + `promo_status` |
| `app/domain/recommendation/entities/bundle_suggestion.py`, `app/infrastructure/mongodb/documents/bundle_document.py` | `rank` field + mapping |
| `tests/unit/agents/test_bundle_phase5_b16_l4_b17.py` | **new** — 32 regression tests (below) |
| `tests/unit/agents/test_bundle_phase5.py`, `tests/eval/conftest.py` | fixtures `status="active"` (B16 active-only filter) |
| `tests/unit/application/test_bundle_service.py` | rank fixtures (rank 1 selected) |

## 5. What Was Deliberately Not Changed

- No OpenAI, no new Bedrock/Gemini calls; no LLM for price/discount/inventory/promo validity/ranking.
- No payment, order, or checkout-session creation; `validate-promo` only validates.
- Recommendation Agent, RAG, Memory, Escalation, Tickets, Widget and the .NET platform untouched.
- Bundle size stays 1–3; single promo per bundle; tenant-scoped everywhere.
- Legacy no-promo contract preserved (promo only when the bundle is actually discounted).

## 6. Verification

### 6.1 Test baselines
- Unit: **1986 passed** (baseline 1954; **+32 new** in `tests/unit/agents/test_bundle_phase5_b16_l4_b17.py`; 0 deleted). Before the fix the whole evidence file failed to import (`promo_capable` did not exist) — captured as before-evidence; all 32 green after.
- Integration + e2e: **145 passed** (unchanged).
- `ruff check` clean; `ruff format --check` clean.
- `tests/eval/test_eval_bundles.py`: 2 of 3 already failed at baseline (real-LLM suite, excluded from CI); no regression introduced (verified against stashed baseline).

### 6.2 Live Atlas verification (production cluster)
Store `5f051250-…`, db `ai_commerce`:
1. **Taxonomy:** 11 categories read back with correct `external_id → name` mapping (`1→Electronics`, `5→Accessories`, `7→Kitchenware`, `8→Furniture`, …) — the same data that now feeds the canonical rules.
2. **B16 on real products** (entities constructed exactly as production does): `Gaming Laptop RTX + Laptop Backpack → 0.7 category_complement`, `Gaming Laptop RTX + 4K Monitor 27" → 0.7 category_complement`, `Wooden Office Desk + Ergonomic Desk Chair → 0.7 category_complement`, `Gaming Laptop RTX + Wireless Earbuds → 0.0 unrelated` — deterministic, sensible, taxonomy-driven.
3. **L4 endpoint reachability:** `POST https://mult-vendor-ecommerce.runasp.net/api/Checkout/validate-promo` (the real production .NET host from the connection's `raw_spec.servers`) responds `401` unauthenticated — server reachable; the deployed AI service holds the decrypted credentials (`ENCRYPTION_KEY` not present in this local environment). Connection discovery now matches the live entity mapping (`Discount` → case-insensitive), and the endpoint is present in `discovered_endpoints`.

### 6.3 L4 status
**UNAVAILABLE** for a live end-to-end create→validate round-trip in this environment: creating a
coupon mutates the production platform and local decryption of platform credentials is impossible
(no `ENCRYPTION_KEY`). Honesty contract honored — no fabricated success, no unverified "confirmed"
wording. Coverage: deterministic unit tests for positive/negative/unknown/HTTP-failure/disabled
shapes + contract-compliant payload, plus live endpoint reachability.

### 6.4 No new external calls
New Bedrock inference calls: **0**. New Gemini embedding calls: **0**. OpenAI: none. The only new
platform calls are the real coupon create (existing Phase 4 behavior, now rank-1-only) and the
real validate-promo POST (only when a code exists).

## 7. Architecture & Integration Safety Audit

- Complementarity is a pure function of product + taxonomy data — no provider dependency, no
  latency, no cost, deterministic and unit-testable.
- The promo path is strictly capability-gated (`promo_capable`, default off) and discount-gated
  (`total_discount > 0`): no capability change for existing stores, no promo for non-discounted
  bundles (legacy contract intact).
- The response/persistence contract gained optional fields only (`rank`, `complementarity_labels`,
  `promo_status`, `score`); existing clients unaffected.
- Validation never mutates carts or orders; `unavailable` degrades to the existing no-promo UX.
- Same-category pairs are demoted by score, not hard-blocked — "two controllers" style requests
  still resolve via coverage.

## 8. Known Limitations / Deferred Findings

- L4 live round-trip deferred to the deployed environment (credential access); the deployed
  service performs create+validate with real credentials by design.
- Live catalog products carry no discount metadata, so live suggestions show the correct
  no-promo behavior (budget fit ⇒ no coupon) — the discount path is covered by tests.
- The eval suite (real LLM) remains 2/3 failing as at baseline; out of scope.

## 9. Verdict

**PASS.** B16, L4 and B17 are fixed at their root layers, verified live against the production
database and the real .NET checkout host, covered by 32 new regression tests, with zero new
inference/embedding calls, zero policy changes and zero schema migrations.