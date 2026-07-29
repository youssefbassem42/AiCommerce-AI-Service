# End-to-End Test Scenarios

## Environment
- Server: `http://localhost:8000`
- Auth: `JWT_REQUIRED=False` — no token needed
- DB: MongoDB `ai_commerce` on `localhost:27018`
- LLM: OpenRouter (`openai/gpt-4o-mini`)
- Qdrant: NOT running — RAG/knowledge endpoints will fail

## Pre-seeded Data
- 1 user, 1 product ("Premium UI Kit Pro" — $49.99 Standard License), 0 orders
- Existing integration connection for DigitalHippo spec (5 entities: user, product, order, media, product_file)

---

## Persona 1 — Store Owner Integration

### 1. Upload OpenAPI Spec — Raw Upload
```bash
curl -s -X POST http://localhost:8000/api/v1/integration/schemas/upload \
  -F "file=@../../openapi.yaml" \
  -F "platform_name=DigitalHippo" | jq .
```
**Expected:** `201` with `schema_id`, `endpoint_count`. Verify `integration_connections` collection updated.

### 2. Upload OpenAPI Spec — Agent Parse
```bash
curl -s -X POST http://localhost:8000/api/v1/integration/schemas/agent-parse \
  -H "Content-Type: application/json" \
  -d '{
    "raw_spec": '$(
      python3 -c "import yaml,json; print(json.dumps(yaml.safe_load(open('../../openapi.yaml'))))"
    )',
    "platform_name": "DigitalHippo",
    "store_id": "store_digitalhippo_001",
    "organization_id": "org_digitalhippo_001"
  }' | jq .
```
**Expected:** `201` with `report` containing entities (product, order, user, media, product_file), feature analysis, capability map with `has_products: true`, `has_orders: true`, `has_categories: false`, `has_inventory: false`, `has_reviews: false`.

### 3. Store Capability Cross-Reference (Manual Verification)
Run the agent parse (Step 2) and verify the returned `capabilities` dict includes ALL of:
- `has_products`, `has_orders`, `has_customers`, `has_promo_codes`, `has_discounts`
- `has_gift_cards`, `has_categories`, `has_variants`, `has_refunds`
- `has_webhooks`, `has_payments`, `has_shipments`, `has_taxes`
- `has_shipping_zones`, `has_locations`, `has_inventory`, `has_reviews`
- `has_content_management`, `has_store_settings`, `has_analytics`
- `has_email_marketing`, `has_abandoned_cart`, `has_wishlist`

**Expected:** `has_products=true`, `has_orders=true`, `has_customers=true`. Most others `false` (DigitalHippo is a digital downloads platform — no inventory, shipping, reviews, etc.).

### 4. Feature Gap Report — UI Kits Category Only
From the agent parse report, check `feature_analysis.unsupported_features` includes:
- `inventory_management` — DigitalHippo doesn't track stock (digital goods)
- `reviews_and_ratings` — no review endpoints
- `shipping_and_taxes` — no shipping zones or tax endpoints
- `marketing_coupons` — no coupon/discount endpoints in the spec

**Not expected** but should be listed if absent: `gift_cards`, `content_management`, `analytics`,
`email_marketing`, `abandoned_cart`, `wishlist`

### 5. List Integration Connections
```bash
curl -s http://localhost:8000/api/v1/integration/connections | jq .
```
**Expected:** `200` with array containing at least 1 connection for `digitalhippo`.

### 6. Get Connection Details
```bash
curl -s http://localhost:8000/api/v1/integration/connections/<CONNECTION_ID> | jq .
```
**Expected:** `200` with full connection including entity mappings, discovered endpoints, field mappings.

### 7. Delete Connection (Cleanup / Re-run)
```bash
curl -s -X DELETE http://localhost:8000/api/v1/integration/connections/<CONNECTION_ID> | jq .
```
**Expected:** `200` with success message.

---

## Persona 2 — Consumer / Customer Interaction

### 8. AI Chat — E-commerce System Prompt
```bash
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What can you help me with?"}],
    "model": "openai/gpt-4o-mini"
  }' | jq .
```
**Expected:** `200`. Response should mention e-commerce topics (products, orders, catalog, etc.) — proving the e-commerce system prompt was injected.

### 9. AI Chat — Product Recommendation Query
```bash
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are an e-commerce assistant for DigitalHippo."},
      {"role": "user", "content": "What UI kits do you recommend for a web developer building a dashboard?"}
    ],
    "model": "openai/gpt-4o-mini"
  }' | jq .
```
**Expected:** `200`. Response should recommend "Premium UI Kit Pro" or similar digital design assets.

### 10. AI Chat — Order Status Query
```bash
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "How can I check the status of my order?"}
    ],
    "model": "openai/gpt-4o-mini"
  }' | jq .
```
**Expected:** `200`. Response should explain order checking process (login, my orders page, etc.).

### 11. AI Chat — Discount / Promo Code Info
```bash
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Do you have any discount codes or promotions available?"}
    ],
    "model": "openai/gpt-4o-mini"
  }' | jq .
```
**Expected:** `200`. Honest response about promo code availability.

### 12. AI Chat — Neutral Sentiment (Informational)
```bash
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What file formats are your products available in?"}
    ],
    "model": "openai/gpt-4o-mini"
  }' | jq .
```
**Expected:** `200`. Neutral, factual response about digital product formats.

### 13. AI Chat — Negative Sentiment (Frustrated User)
```bash
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I paid for a product but the download link is broken. This is really frustrating!"}
    ],
    "model": "openai/gpt-4o-mini"
  }' | jq .
```
**Expected:** `200`. Empathetic, apologetic response. Should offer troubleshooting steps and mention contact support.

### 14. AI Chat — Positive Sentiment (Happy User)
```bash
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I love the Premium UI Kit! The components are amazing and saved me so much time. Do you have any other similar products?"}
    ],
    "model": "openai/gpt-4o-mini"
  }' | jq .
```
**Expected:** `200`. Grateful, energetic response. Should mention the current product catalog and suggest categories (ui_kits, icons).

### 15. AI Chat — Streaming with System Prompt Injection
```bash
curl -s -N -X POST http://localhost:8000/api/v1/ai/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Tell me about your product categories."}],
    "model": "openai/gpt-4o-mini"
  }'
```
**Expected:** SSE stream with `data:` events. Final event should contain metadata (no auto-ticket since Qdrant isn't used here).

### 16. Bundle Recommendation — Two Products That Complement
Since the DB has only 1 product, ask for bundling with what exists:
```bash
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What products would you recommend bundling together for a complete web development toolkit?"}
    ],
    "model": "openai/gpt-4o-mini",
    "temperature": 0.7
  }' | jq .
```
**Expected:** `200`. Should mention "Premium UI Kit Pro" and suggest complementary products (icon packs, templates). The response should describe bundle structure (items, suggested savings, use cases).

### 17. Bundle Recommendation — Price-Aware Bundle
```bash
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I have a budget of $100. Can you recommend a bundle of UI kits and icons that would give me the best value?"}
    ],
    "model": "openai/gpt-4o-mini",
    "temperature": 0.7
  }' | jq .
```
**Expected:** `200`. Bundle suggestion within budget. Should list items, individual prices vs. bundle price, and savings.

---

## RAG / Knowledge Flow (Requires Qdrant)

### 18. RAG Chat — Knowledge Base Query (WILL FAIL WITHOUT QDRANT)
```bash
curl -s -X POST http://localhost:8000/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is your refund policy?",
    "store_id": "store_digitalhippo_001",
    "organization_id": "org_digitalhippo_001"
  }' | jq .
```
**Expected:** `500` — Qdrant connection error. After Qdrant is running and FAQ is uploaded, expected: `200` with `response`, `citations`, `confidence_score`.

### 19. RAG Chat — Explicit Escalation Request (Creates Ticket)
```bash
curl -s -X POST http://localhost:8000/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Please create a support ticket. I need a human to help me with my billing issue.",
    "store_id": "store_digitalhippo_001",
    "organization_id": "org_digitalhippo_001",
    "customer_id": "customer_001"
  }' | jq .
```
**Expected:** `200`. Response should acknowledge the request and indicate a ticket was created (check `ticket_analysis` collection for new document).

### 20. RAG Chat — No Auto-Escalation for Low Confidence (Just Inform)
```bash
curl -s -X POST http://localhost:8000/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can you tell me about your enterprise pricing plans?",
    "store_id": "store_digitalhippo_001",
    "organization_id": "org_digitalhippo_001",
    "customer_id": "customer_002"
  }' | jq .
```
**Expected:** `200` with low confidence score. **Should NOT create a ticket** — the response should simply say the AI couldn't find the information. Verify no new ticket was created for customer_002.

### 21. RAG Chat — Positive Sentiment Question
```bash
curl -s -X POST http://localhost:8000/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "The product download was quick and easy. How do I leave a review?",
    "store_id": "store_digitalhippo_001",
    "organization_id": "org_digitalhippo_001",
    "customer_id": "customer_003"
  }' | jq .
```
**Expected:** `200` (may have low confidence if no FAQ content covers reviews). Positive tone in response.

### 22. RAG Chat — Neutral Sentiment Question
```bash
curl -s -X POST http://localhost:8000/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What payment methods do you accept?",
    "store_id": "store_digitalhippo_001",
    "organization_id": "org_digitalhippo_001",
    "customer_id": "customer_004"
  }' | jq .
```
**Expected:** `200` — neutral, factual response about payment methods (Stripe).

### 23. RAG Chat — Negative Sentiment Question
```bash
curl -s -X POST http://localhost:8000/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I was charged twice for my order and need a refund immediately!",
    "store_id": "store_digitalhippo_001",
    "organization_id": "org_digitalhippo_001",
    "customer_id": "customer_005"
  }' | jq .
```
**Expected:** `200` — empathetic, apologetic, and action-oriented. Should **not** auto-escalate to a ticket unless the user explicitly requests human help. Since this user says "need a refund" but doesn't say "talk to a human" or "create a ticket", no auto-ticket should be created.

### 24. RAG Chat — Explicit Escalation + Negative Sentiment
```bash
curl -s -X POST http://localhost:8000/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I was charged twice and I want to speak to a human right now! Create a support ticket.",
    "store_id": "store_digitalhippo_001",
    "organization_id": "org_digitalhippo_001",
    "customer_id": "customer_006"
  }' | jq .
```
**Expected:** `200`. Response acknowledges frustration AND confirms ticket was created. Verify `ticket_analysis` collection.

### 25. RAG Chat — Streaming Variant
```bash
curl -s -N -X POST http://localhost:8000/rag/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me about your shipping times.",
    "store_id": "store_digitalhippo_001",
    "organization_id": "org_digitalhippo_001"
  }'
```
**Expected:** SSE stream of content chunks, then a final metadata chunk with confidence_score.

---

## Bundle Verification (Assertion Details)

When testing bundles (Scenarios 16 and 17), verify the following in the response:

1. **Status code** MUST be `200`
2. **Response message** should be a non-empty string
3. **Bundle structure** — the response should:
   - List specific products/items (at least one match from the catalog)
   - Describe why they complement each other
   - Mention pricing or value (for price-aware bundle, respect budget)
   - Use encouraging, helpful language

**Example assertion** (not test code, but what to manually check):
```
✓ Status = 200
✓ Response contains "Premium UI Kit Pro"
✓ Response describes complementary use
✓ Response mentions pricing or value
✓ Language is positive and helpful
✓ No errors in response
```

## Sentiment-Specific Assertions

| Scenario | Sentiment | Expected Tone | Expected Actions |
|----------|-----------|---------------|------------------|
| 12 | Neutral | Factual, informative | List features, answer directly |
| 13 | Negative | Empathetic, apologetic | Troubleshoot, offer solutions |
| 14 | Positive | Energetic, grateful | Recommend more products, engage |
| 23 | Negative | Empathetic, apologetic | Address refund concern, guide to contact |
| 24 | Negative + Escalation | Empathetic + Action | Create ticket, acknowledge frustration |

## Ticket Escalation Behavior

| Request Keywords | Confidence | Result |
|-----------------|------------|--------|
| None (normal Q) | Any | No ticket |
| Low confidence Q | Low (<0.3) | No ticket — just inform user |
| "Talk to a human", "create a ticket", "escalate" | Any | Ticket created |
| "I need a refund" (no escalation keywords) | Low | No ticket — just helpful guidance |
| "Speak to support", "contact support" | Any | Ticket created |
