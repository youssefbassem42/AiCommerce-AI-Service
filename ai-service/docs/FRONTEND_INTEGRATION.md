# AI Service — Frontend Integration Map

> Endpoint-by-endpoint mapping with recommended screens, buttons, layouts, and components.

---

## 1. Core AI Chat

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 1.1 | `/api/v1/ai/chat` | POST | Authorization header | `{messages: [{role, content}], model, temperature?, max_tokens?, tools?, json_mode?}` | `{id, model, provider, message, usage, latency_ms}` |
| 1.2 | `/api/v1/ai/chat/stream` | POST | Authorization header | `{messages, model, ...}` | SSE stream: `{id, content, finish_reason}` chunks |
| 1.3 | `/api/v1/ai/chat/structured` | POST | Authorization header | `{messages, model, schema_definition: {...}}` | `ChatResponseSchema` |
| 1.4 | `/api/v1/ai/chat/tools` | POST | Authorization header | `{messages, model, tools: [{name, description, parameters}]}` | `ChatResponseSchema` |
| 1.5 | `/api/v1/ai/embeddings` | POST | Authorization header | `{input: str\|[str], model}` | `{model, provider, embeddings: [[float]], usage}` |
| 1.6 | `/api/v1/ai/models` | GET | Authorization header | — | `[{name, provider, capabilities, context_length, pricing}]` |
| 1.7 | `/api/v1/ai/providers` | GET | Authorization header | — | `[{provider, supported_models, capabilities}]` |
| 1.8 | `/api/v1/ai/health` | GET | Authorization header | — | `{status, provider, latency_ms}` |
| 1.9 | `/api/v1/ai/provider/{provider}/models` | GET | Authorization header, provider path | — | `[model_name strings]` |
| 1.10 | `/api/v1/ai/provider/{provider}/health` | GET | Authorization header, provider path | — | `{status, provider, latency_ms}` |

**Frontend:**
- **1.1** → `AiChatScreen` — full chat UI, message bubbles, input bar, send btn, model selector dropdown, token usage badge
- **1.2** → Same as 1.1 with streaming text animation / typing indicator (use `ReadableStream`)
- **1.3** → `DataExtractionScreen` — form submits data, card shows extracted result matching schema
- **1.4** → `ToolChatScreen` — chat + tool call cards with function result accordion
- **1.5** → Internal / no direct UI (used by knowledge pipelines)
- **1.6** → `ModelSelector` dropdown, settings page card listing capabilities
- **1.7** → `ProviderSelector` — grid of provider cards with status badge (green/red dot)
- **1.8–1.10** → `StatusDot` component in admin navbar, provider detail view

---

## 2. Simple Chat

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 2.1 | `/chat` | POST | Authorization header | `{message: string}` | `{response: string}` |

**Frontend:** Minimal embedded chat widget — floating FAB btn → bottom sheet, no model selection.

---

## 3. Commerce (Products / Categories / Orders / Inventory)

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 3.1 | `POST /api/v1/commerce/products` | POST | Authorization header | `{store_id, title, status?, variants, images, tags?, ...}` | Full product object |
| 3.2 | `GET /api/v1/commerce/products/{product_id}` | GET | Authorization header, product_id | — | Full product object |
| 3.3 | `GET /api/v1/commerce/products` | GET | Authorization header, page, page_size, store_id?, status? | — | Paginated product list |
| 3.4 | `PUT /api/v1/commerce/products/{product_id}` | PUT | Authorization header, product_id | Partial product fields | Updated product |
| 3.5 | `DELETE /api/v1/commerce/products/{product_id}` | DELETE | Authorization header, product_id | — | `{success: bool}` |
| 3.6 | `POST /api/v1/commerce/categories` | POST | Authorization header | `{name, parent_id?, store_id, ...}` | Full category object |
| 3.7 | `GET /api/v1/commerce/categories` | GET | Authorization header, page, page_size, store_id? | — | Paginated category list |
| 3.8 | `GET /api/v1/commerce/categories/{category_id}` | GET | Authorization header, category_id | — | Category object |
| 3.9 | `GET /api/v1/commerce/categories/{category_id}/children` | GET | Authorization header, category_id | — | `[Category]` |
| 3.10 | `GET /api/v1/commerce/categories/root/{store_id}` | GET | Authorization header, store_id | — | `[Category]` — root-level only |
| 3.11 | `PUT /api/v1/commerce/categories/{category_id}` | PUT | Authorization header, category_id | Partial category fields | Updated category |
| 3.12 | `DELETE /api/v1/commerce/categories/{category_id}` | DELETE | Authorization header, category_id | — | `{success: bool}` |
| 3.13 | `POST /api/v1/commerce/orders` | POST | Authorization header | `{store_id, customer_id, line_items, ...}` | Full order object |
| 3.14 | `GET /api/v1/commerce/orders/{order_id}` | GET | Authorization header, order_id | — | Order object |
| 3.15 | `GET /api/v1/commerce/orders` | GET | Authorization header, page, page_size, store_id?, customer_id? | — | Paginated order list |
| 3.16 | `PUT /api/v1/commerce/orders/{order_id}/status` | PUT | Authorization header, order_id | `{status}` | Updated order |
| 3.17 | `POST /api/v1/commerce/inventory` | POST | Authorization header | `{variant_id, store_id, quantity, ...}` | Inventory record |
| 3.18 | `GET /api/v1/commerce/inventory/{variant_id}` | GET | Authorization header, variant_id, store_id (query) | — | Inventory record |
| 3.19 | `GET /api/v1/commerce/inventory` | GET | Authorization header, page, page_size, store_id? | — | Paginated inventory list |
| 3.20 | `PUT /api/v1/commerce/inventory/{variant_id}` | PUT | Authorization header, variant_id | `{quantity, ...}` | Updated inventory |
| 3.21 | `GET /api/v1/commerce/inventory/low-stock/{store_id}` | GET | Authorization header, store_id, threshold? (default:10) | — | `[Inventory items below threshold]` |

**Frontend:**
- **3.1** → `ProductCreateScreen` — multi-section form: General (title, desc, type, vendor), Media (image upload gallery), Variants (dynamic add/remove: price, SKU, stock), SEO, Tags chips
- **3.2** → `ProductDetailScreen` — image carousel card, info card, variant selector, spec table, tags row
- **3.3** → `ProductListScreen` — data table, search bar, status filter tabs (All/Draft/Active/Archived), pagination
- **3.4** → Same as create but pre-filled; Save btn triggers PUT
- **3.5** → Confirmation dialog / modal with Delete danger btn
- **3.6–3.12** → `CategoryTreeScreen` — nested tree with expand/collapse, inline edit side panel, Add Root / Add Child / Delete btns, breadcrumb nav
- **3.13** → `NewOrderScreen` — customer search, product search + add line items, quantity stepper, price summary card, Place Order btn
- **3.14** → `OrderDetailScreen` — info card (status badge, dates, totals), line items table, customer card, timeline
- **3.15** → `OrderListScreen` — filterable table with status chips, customer search, date range picker
- **3.16** → Status dropdown / quick-action btns on order detail row
- **3.17–3.19** → `InventoryScreen` — table with variant, quantity, location columns, batch edit mode
- **3.20** → Inline quantity input with +/- stepper, confirm via PUT
- **3.21** → `LowStockAlertCard` — red-tinted card list with Order More action btn; dashboard widget with count badge

---

## 4. Knowledge Base (Unified)

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 4.1 | `POST /api/v1/knowledge-base/upload` | POST | Auth, multipart file | file + query: store_id, uploaded_by, org_id | Upload record |
| 4.2 | `GET /api/v1/knowledge-base/documents` | GET | Auth, page, page_size, store_id?, status? | — | Paginated document list |
| 4.3 | `GET /api/v1/knowledge-base/documents/{document_id}` | GET | Auth, document_id | — | Document metadata + status |
| 4.4 | `DELETE /api/v1/knowledge-base/documents/{document_id}` | DELETE | Auth, document_id | — | `{success: bool}` |
| 4.5 | `POST /api/v1/knowledge-base/process` | POST | Auth | `{document_id, file_path, also_chunk?, strategy?, chunk_size?, overlap?}` | `AsyncJobAcceptedResponse` |
| 4.6 | `POST /api/v1/knowledge-base/chunk` | POST | Auth | `{document_id, strategy?, chunk_size?, overlap?}` | `AsyncJobAcceptedResponse` |
| 4.7 | `POST /api/v1/knowledge-base/embed` | POST | Auth | `{document_id, model?, sync_to_vector_store?}` | `AsyncJobAcceptedResponse` |
| 4.8 | `POST /api/v1/knowledge-base/search` | POST | Auth | `{query, top_k?, score_threshold?, store_id?}` | `{results: [{chunk_id, document_id, content, score}]}` |
| 4.9 | `POST /api/v1/knowledge-base/search/hybrid` | POST | Auth | Same as search | Same as search |
| 4.10 | `POST /api/v1/knowledge-base/summary` | POST | Auth, store_id query | `{model?, temperature?, max_tokens?}` | Generated business summary |
| 4.11 | `POST /api/v1/knowledge-base/summary/regenerate` | POST | Auth, store_id query | Same as summary | Regenerated summary |
| 4.12 | `GET /api/v1/knowledge-base/jobs/{job_id}` | GET | Auth, job_id | — | `{id, status, progress, error_message?}` |

**Frontend:**
- **4.1** → `KnowledgeUploadScreen` — file dropzone card, metadata form (store, scope), Upload & Process toggle btn, progress bar
- **4.2–4.3** → `DocumentListScreen` — file list/grid with status badges (pending/processing/ready/error), search + filter bar
- **4.4** → Swipe-to-delete or long-press context menu with confirmation
- **4.5–4.7** → Action btns on each document row: Process / Chunk / Embed — each triggers async job, poll 4.12 for progress
- **4.8–4.9** → `KnowledgeSearchScreen` — search bar, results list with relevance score bar, snippet preview, document link
- **4.10–4.11** → `BusinessSummaryCard` — rendered markdown card, Regenerate btn, version history dropdown
- **4.12** → `JobStatusBadge` component (reusable); `JobMonitorScreen` with progress bars table

---

## 5. RAG Chat

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 5.1 | `/rag/chat` | POST | Auth | `{message, store_id, model?, top_k?, use_hybrid?, knowledge_scope?}` | `{response, citations, confidence_score, latency_ms, usage}` |
| 5.2 | `/rag/chat/stream` | POST | Auth | Same with stream: true | SSE stream |

**Frontend:** `RAGChatScreen` — chat UI + citation cards (expandable "View Sources" accordion) below each bot message, confidence score colored dot (green/yellow/red), store picker in header.

---

## 6. Recommendations

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 6.1 | `POST /api/v1/recommendations/chat` | POST | Auth | `{message, store_id, customer_id?}` | `{products: [{product_id, title, price, image_url, match_reasons}], rationale, latency_ms}` |
| 6.2 | `POST /api/v1/recommendations/bundle-suggestion` | POST | Auth | `{message, store_id, customer_id?}` | `{budget, bundles: [{products, total_after_discount, remaining_budget, within_budget, promo_code?}], rationale}` |

**Frontend:**
- **6.1** → `ProductRecommendationScreen` — chat-like input "What are you looking for?" → product card grid (image, title, price, match reasons badges). Ask AI FAB btn throughout shopping experience.
- **6.2** → `BundleSuggestionScreen` — input "I have $X and need Y" → side-by-side bundle comparison cards: product list with strikethrough pricing, discount %, total savings, remaining budget progress bar, Copy Bundle btn, promo code badge

---

## 7. Admin — Bundle Analytics

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 7.1 | `POST /api/v1/admin/bundles/track` | POST | Auth | `{store_id, bundle_key, products, total_after_discount, action?}` | `{tracked: true, bundle_key}` |
| 7.2 | `GET /api/v1/admin/bundles/tracking` | GET | Auth, store_id, top_only? | — | `[{bundle_key, products, copy_count, ...}]` |
| 7.3 | `GET /api/v1/admin/bundles/tracking/{bundle_key}` | GET | Auth, bundle_key, store_id | — | Single tracking record |
| 7.4 | `POST /api/v1/admin/bundles/top/promote` | POST | Auth | `{bundle_key, store_id}` | `{status: "promoted", bundle_key}` |
| 7.5 | `DELETE /api/v1/admin/bundles/top/{bundle_key}` | DELETE | Auth, bundle_key, store_id | — | `{status: "demoted", bundle_key}` |
| 7.6 | `GET /api/v1/admin/bundles/config` | GET | Auth, store_id | — | `{auto_track, max_top_bundles, ...}` |
| 7.7 | `PUT /api/v1/admin/bundles/config` | PUT | Auth | `{auto_track?, max_top_bundles?, ...}` | Updated config |

**Frontend:** `BundleAnalyticsDashboard` — sortable data table (bundle, copy count, conversion), Promote to Top toggle btn per row, `TopBundlesCarousel`, Settings cog → config form card.

---

## 8. Auth & API Keys

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 8.1 | `GET /api/v1/auth/api-keys/{store_id}` | GET | Auth, store_id | — | `{api_keys: [{id, name, scopes, last_used_at}]}` |
| 8.2 | `POST /api/v1/auth/api-keys` | POST | Auth | `{store_id, name, scopes, expires_at?}` | `{key: "sk-...", id, name, scopes}` |
| 8.3 | `DELETE /api/v1/auth/api-keys/{key_id}` | DELETE | Auth, key_id | — | 204 No Content |
| 8.4 | `GET /api/v1/auth/audit-logs` | GET | Auth, skip?, limit? | — | `[{action, user_id, timestamp, details}]` |

**Frontend:**
- **8.1–8.3** → `ApiKeyManagerScreen` — table (name, masked key `sk-****ab12`, scopes chips, last used, created), Generate Key btn → modal with scope checkboxes → reveal once with copy btn, Revoke confirmation dialog
- **8.4** → `AuditLogScreen` — log table with search/filter

---

## 9. Tickets (Customer Support)

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 9.1 | `POST /api/v1/tickets` | POST | Auth | `{store_id, customer_id, messages}` | `{id, ticket_id, sentiment, category, summary, priority, suggested_response, ...}` |
| 9.2 | `GET /api/v1/tickets/{ticket_id}` | GET | Auth, ticket_id | — | Full ticket + customer profile + recent orders |
| 9.3 | `GET /api/v1/tickets` | GET | Auth, store_id, status?, priority?, sentiment?, page, page_size | — | `{items: [TicketResponse], total, page, page_size}` |
| 9.4 | `PATCH /api/v1/tickets/{ticket_id}/status` | PATCH | Auth, ticket_id | `{status: open\|in_progress\|resolved\|closed}` | Updated ticket |
| 9.5 | `DELETE /api/v1/tickets/{ticket_id}` | DELETE | Auth, ticket_id | — | `{success: bool}` |

**Frontend:**
- **9.1** → `NewTicketScreen` — customer search + message input + submit btn
- **9.2** → `TicketDetailScreen` — header card (sentiment icon, priority badge, status chip), AI summary card, suggested response with Use btn, customer info card, recent orders expandable list, conversation timeline
- **9.3** → `TicketListScreen / HelpDeskDashboard` — kanban board (Open / In Progress / Resolved / Closed) or filterable table with filter chips for priority & sentiment
- **9.4** → Quick-action btns: Resolve, Close, Reopen
- **9.5** → Danger btn in detail screen with confirmation dialog

---

## 10. Integration (Platform Connectors)

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 10.1 | `POST /api/v1/integration/schemas/parse` | POST | Auth | `{platform_name, raw_spec: {...}}` | Parsed schema result |
| 10.2 | `POST /api/v1/integration/schemas/agent-parse` | POST | Auth | `{platform_name, raw_spec}` | AI-parsed schema |
| 10.3 | `POST /api/v1/integration/agent-sync` | POST | Auth | `{platform_name, raw_spec, store_id, credentials?, auto_sync?}` | Full sync result |
| 10.4 | `POST /api/v1/integration/connections` | POST | Auth | `{store_id, platform_name, name, auth_config?, entity_mappings?}` | Connection record |
| 10.5 | `GET /api/v1/integration/connections` | GET | Auth, store_id, page, page_size | — | Paginated connection list |
| 10.6 | `GET /api/v1/integration/connections/{connection_id}` | GET | Auth, connection_id | — | Full connection |
| 10.7 | `PUT /api/v1/integration/connections/{connection_id}/mappings` | PUT | Auth, connection_id | `{entity_mappings: [...]}` | Updated connection |
| 10.8 | `PUT /api/v1/integration/connections/{connection_id}/credentials` | PUT | Auth, connection_id | `{credentials: {...}}` | Updated connection |
| 10.9 | `POST /api/v1/integration/connections/{connection_id}/sync` | POST | Auth, connection_id | `{full_sync?: bool}` | Sync status |
| 10.10 | `DELETE /api/v1/integration/connections/{connection_id}` | DELETE | Auth, connection_id | — | `{success: bool}` |

**Frontend:** `IntegrationHubScreen` — grid of available platform cards (Shopify, WooCommerce...), Connect btn → OAuth/form for credentials. Connection detail: entity mapping editor (drag-drop field pairs), Sync Now btn with last-sync timestamp badge, status indicator (connected/error/syncing).

---

## 11. Knowledge Jobs

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 11.1 | `POST /knowledge/jobs/document-processing` | POST | Auth, document_id, file_path (query) | — | `JobCreateResponse` |
| 11.2 | `POST /knowledge/jobs/chunk-generation` | POST | Auth, document_id (query) | — | `JobCreateResponse` |
| 11.3 | `POST /knowledge/jobs/summary-generation` | POST | Auth, store_id (query) | — | `JobCreateResponse` |
| 11.4 | `POST /knowledge/jobs/embedding-generation` | POST | Auth, chunk_ids (query) | — | `JobCreateResponse` |
| 11.5 | `POST /knowledge/jobs/vector-sync` | POST | Auth, chunk_ids (query) | — | `JobCreateResponse` |
| 11.6 | `GET /knowledge/jobs/{job_id}` | GET | Auth, job_id | — | `JobResponse` |
| 11.7 | `GET /knowledge/jobs` | GET | Auth, page, page_size, status?, job_type? | — | Paginated job list |
| 11.8 | `POST /knowledge/jobs/{job_id}/requeue` | POST | Auth, job_id | — | Requeued job |

**Frontend:** `JobQueueScreen` — data table with job type icon, status progress bar, retry btn for failed, filter by job type/status tabs.

---

## 12. Knowledge Retrieval (Standalone)

| # | Endpoint | Method | Required | Request Body | Response Body |
|---|----------|--------|----------|-------------|--------------|
| 12.1 | `POST /knowledge/retrieval/search` | POST | Auth | `{query, top_k?, score_threshold?, use_hybrid?, use_mmr?, rerank?, store_id?}` | `RetrievalResponse` |

**Frontend:** Reused via RAG chat; standalone `SemanticSearchScreen` with results list and relevance slider filter.

---

## 13. General

| # | Endpoint | Method | Required | Response |
|---|----------|--------|----------|---------|
| 13.1 | `GET /health/` | GET | none | `{status: "AI Service is live !"}` |

**Frontend:** Bootstrap health check, no visible UI.

---

## Screen Map Summary

| Screen | Primary Endpoints | Layout |
|--------|-------------------|--------|
| **AiChatScreen** | 1.1, 1.2 | Full page chat + sidebar model config |
| **RAGChatScreen** | 5.1, 5.2 | Full page chat + source citation accordion |
| **ProductRecommendationScreen** | 6.1 | Chat input + product card grid |
| **BundleSuggestionScreen** | 6.2 | Input → side-by-side bundle comparison cards |
| **ProductListScreen** | 3.3 | Data table + filter bar + pagination |
| **ProductDetailScreen** | 3.2, 3.4 | Image carousel card + info card + variant selector |
| **ProductCreateScreen** | 3.1 | Multi-section form + dynamic variant rows |
| **CategoryTreeScreen** | 3.6–3.12 | Nested tree + inline edit side panel |
| **OrderListScreen** | 3.15 | Table with status chips + filters |
| **OrderDetailScreen** | 3.14 | Detail cards + line items table + timeline |
| **InventoryScreen** | 3.19, 3.20, 3.21 | Table + low-stock alert cards |
| **TicketListScreen / HelpDesk** | 9.3 | Kanban board OR filterable table |
| **TicketDetailScreen** | 9.2, 9.4 | AI summary card + timeline + action btns |
| **KnowledgeUploadScreen** | 4.1 | File dropzone + metadata form + progress |
| **DocumentListScreen** | 4.2, 4.3 | File list with status badges + action btns |
| **BusinessSummaryCard** | 4.10, 4.11 | Rendered markdown card + regenerate btn |
| **KnowledgeSearchScreen** | 4.8, 4.9 | Search bar + results list with relevance bars |
| **JobMonitorScreen** | 11.6, 11.7 | Progress bars table + status filter |
| **JobQueueScreen** | 11.1–11.8 | Table + job type icons + retry btns |
| **ApiKeyManagerScreen** | 8.1–8.3 | Table + generate modal + revoke confirm |
| **AuditLogScreen** | 8.4 | Log table + search/filter |
| **IntegrationHubScreen** | 10.4, 10.5 | Platform grid cards + connection status |
| **BundleAnalyticsDashboard** | 7.1–7.7 | Data table + top bundles carousel + config form |
| **ProviderSelector** | 1.6, 1.7, 1.9 | Card grid with health dots |
| **SettingsScreen** | 1.6, 7.6, 7.7 | Form cards grouped by section |

---

## Reusable Components

| Component | Used By | Description |
|-----------|---------|-------------|
| `StatusBadge` | All screens | Colored chip (green/red/yellow) — health, job, ticket status |
| `StatusDot` | 1.8–1.10, 10.4–10.9 | Small colored circle for provider / connection health |
| `ProductCard` | 6.1, 6.2, 3.3 | Image + title + price + match reasons badges |
| `ProgressBar` | 4.5–4.7, 11.1–11.8 | Job progress 0–100% |
| `CitationAccordion` | 5.1, 5.2, 12.1 | Expandable source list with relevance score |
| `JobActionButton` | 4.5–4.7 | Process / Chunk / Embed with loading spinner |
| `InputBar` | 1.1, 1.2, 5.1, 5.2, 6.1, 6.2 | Message input + send btn |
| `ModelSelector` | 1.1, 1.2, 5.1, 5.2 | Dropdown populated from 1.6 / 1.9 |
| `StorePicker` | 3.x, 4.x, 5.x, 6.x, 9.x | Store ID selector dropdown |
| `DataTable` | 3.3, 3.15, 3.19, 7.2, 8.1, 8.4, 9.3, 11.7 | Reusable sortable/filterable table |
| `ConfirmationDialog` | 3.5, 3.12, 4.4, 8.3, 9.5 | Confirm destructive actions |
| `FilterChips` | 3.3, 9.3, 11.7 | Horizontal scrollable status/type filter chips |
| `EmptyState` | All list screens | Illustration + message when no data |
| `ErrorBoundaryCard` | All detail screens | Retry btn + error message when fetch fails |
