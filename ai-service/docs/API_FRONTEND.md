# API — Frontend Integration Guide

> Complete endpoint reference for the frontend team. Generated from the live API definition.

## 1. Basics

- **Base URL:** `https://aicommerce-ai-service-production.up.railway.app/api/v1` (the simple `/chat` endpoint is at the root)
- **Auth:** every endpoint requires `Authorization: Bearer <token>` (JWT). Role requirements per endpoint below.
- **Auth failures:** `401` plain text (`Missing or invalid Authorization header` / `Invalid or expired token`); `403` `{"detail": "Access denied: no roles assigned"}`
- **Not found:** `404` `{"code": "<ExceptionName>", "message": "<detail>", "details": null}`
- **Validation:** `422` FastAPI standard `{"detail": [{"type", "loc", "msg"}]}`
- **Server error:** `500` `{"code": "internal_error", "message": "Internal server error", "details": null}`
- **Not documented (internal / legacy, do not integrate):** `/health/`, `/knowledge/jobs/*`, `/knowledge/retrieval/search`, `/rag/chat*`

---

## 1. AI Chat & Models

### 1. `POST /api/v1/ai/chat`
*Chat*

**Auth:** Bearer JWT (any authenticated user)

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `messages` | list[Message] | yes |  |
| `model` | str | yes |  |
| `temperature` | float | None | no |  |
| `top_p` | float | None | no |  |
| `max_tokens` | int | None | no |  |
| `stream` | bool | no |  |
| `tools` | list[Tool] | None | no |  |
| `tool_choice` | str | None | no |  |
| `json_mode` | bool | no |  |
```json
{
  "messages": [
    {
      "role": "<string>",
      "content": "<string>",
      "name": "<string>",
      "tool_call_id": "<string>",
      "tool_calls": [
        {
          "id": "<string>",
          "type": "<string>",
          "function_name": "<string>",
          "arguments": "<string>"
        }
      ]
    }
  ],
  "model": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `model` | str | yes |
| `provider` | str | yes |
| `message` | Message | yes |
| `usage` | Usage | yes |
| `latency_ms` | float | yes |
| `metadata` | object | None | no |
```json
{
  "id": "<string>",
  "model": "<string>",
  "provider": "<string>",
  "message": {
    "role": "<string>",
    "content": "<string>",
    "name": "<string>",
    "tool_call_id": "<string>",
    "tool_calls": [
      {
        "id": "<string>",
        "type": "<string>",
        "function_name": "<string>",
        "arguments": "<string>"
      }
    ]
  },
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "cost": 0.0
  },
  "latency_ms": 0.0
}
```

**Frontend:** Main AI chat screen (e-commerce assistant). Message bubbles, input bar, model selector, token usage badge.

### 2. `POST /api/v1/ai/chat/stream`
*Chat Stream*

**Auth:** Bearer JWT (any authenticated user)

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `messages` | list[Message] | yes |  |
| `model` | str | yes |  |
| `temperature` | float | None | no |  |
| `top_p` | float | None | no |  |
| `max_tokens` | int | None | no |  |
| `stream` | bool | no |  |
| `tools` | list[Tool] | None | no |  |
| `tool_choice` | str | None | no |  |
| `json_mode` | bool | no |  |
```json
{
  "messages": [
    {
      "role": "<string>",
      "content": "<string>",
      "name": "<string>",
      "tool_call_id": "<string>",
      "tool_calls": [
        {
          "id": "<string>",
          "type": "<string>",
          "function_name": "<string>",
          "arguments": "<string>"
        }
      ]
    }
  ],
  "model": "<string>"
}
```

**Response `200`:**
```json
{}
```

**Frontend:** Same chat screen with streaming: consume the SSE stream and append chunks as they arrive.

### 3. `POST /api/v1/ai/chat/structured`
*Chat Structured*

**Auth:** Bearer JWT (any authenticated user)

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `messages` | list[Message] | yes |  |
| `model` | str | yes |  |
| `schema_definition` | object | yes |  |
```json
{
  "messages": [
    {
      "role": "<string>",
      "content": "<string>",
      "name": "<string>",
      "tool_call_id": "<string>",
      "tool_calls": [
        {
          "id": "<string>",
          "type": "<string>",
          "function_name": "<string>",
          "arguments": "<string>"
        }
      ]
    }
  ],
  "model": "<string>",
  "schema_definition": "{}"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `model` | str | yes |
| `provider` | str | yes |
| `message` | Message | yes |
| `usage` | Usage | yes |
| `latency_ms` | float | yes |
| `metadata` | object | None | no |
```json
{
  "id": "<string>",
  "model": "<string>",
  "provider": "<string>",
  "message": {
    "role": "<string>",
    "content": "<string>",
    "name": "<string>",
    "tool_call_id": "<string>",
    "tool_calls": [
      {
        "id": "<string>",
        "type": "<string>",
        "function_name": "<string>",
        "arguments": "<string>"
      }
    ]
  },
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "cost": 0.0
  },
  "latency_ms": 0.0
}
```

**Frontend:** Form-to-data screens: submit text, render the structured result as a card matching `schema_definition`.

### 4. `POST /api/v1/ai/chat/tools`
*Chat Tools*

**Auth:** Bearer JWT (any authenticated user)

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `messages` | list[Message] | yes |  |
| `model` | str | yes |  |
| `temperature` | float | None | no |  |
| `top_p` | float | None | no |  |
| `max_tokens` | int | None | no |  |
| `stream` | bool | no |  |
| `tools` | list[Tool] | None | no |  |
| `tool_choice` | str | None | no |  |
| `json_mode` | bool | no |  |
```json
{
  "messages": [
    {
      "role": "<string>",
      "content": "<string>",
      "name": "<string>",
      "tool_call_id": "<string>",
      "tool_calls": [
        {
          "id": "<string>",
          "type": "<string>",
          "function_name": "<string>",
          "arguments": "<string>"
        }
      ]
    }
  ],
  "model": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `model` | str | yes |
| `provider` | str | yes |
| `message` | Message | yes |
| `usage` | Usage | yes |
| `latency_ms` | float | yes |
| `metadata` | object | None | no |
```json
{
  "id": "<string>",
  "model": "<string>",
  "provider": "<string>",
  "message": {
    "role": "<string>",
    "content": "<string>",
    "name": "<string>",
    "tool_call_id": "<string>",
    "tool_calls": [
      {
        "id": "<string>",
        "type": "<string>",
        "function_name": "<string>",
        "arguments": "<string>"
      }
    ]
  },
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "cost": 0.0
  },
  "latency_ms": 0.0
}
```

**Frontend:** Tool-chat screen: chat with tool-call cards (function name + result) rendered as accordions.

### 5. `POST /api/v1/ai/embeddings`
*Embeddings*

**Auth:** Bearer JWT (any authenticated user)

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `input` | str | list[str] | yes |  |
| `model` | str | yes |  |
```json
{
  "input": "<string>",
  "model": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `model` | str | yes |
| `provider` | str | yes |
| `embeddings` | list[list[float]] | yes |
| `usage` | Usage | yes |
```json
{
  "model": "<string>",
  "provider": "<string>",
  "embeddings": [
    "<list[float]>"
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "cost": 0.0
  }
}
```

**Frontend:** Internal utility (embedding pipelines). No direct UI needed.

### 6. `GET /api/v1/ai/health`
*Health*

**Auth:** Bearer JWT (any authenticated user)

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `status` | str | yes |
| `provider` | str | yes |
| `latency_ms` | float | yes |
| `details` | str | None | no |
```json
{
  "status": "<string>",
  "provider": "<string>",
  "latency_ms": 0.0
}
```

**Frontend:** API health indicator (settings page / diagnostics).

### 7. `GET /api/v1/ai/models`
*List Models*

**Auth:** Bearer JWT (any authenticated user)

**Response `200`:** array of objects —
```json
[
  {}
]
```

**Frontend:** Model selector dropdown + model info cards on a settings page.

### 8. `GET /api/v1/ai/provider/{provider}/health`
*Provider Health*

**Auth:** Bearer JWT (any authenticated user)

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `status` | str | yes |
| `provider` | str | yes |
| `latency_ms` | float | yes |
| `details` | str | None | no |
```json
{
  "status": "<string>",
  "provider": "<string>",
  "latency_ms": 0.0
}
```

**Frontend:** Provider status dot in the admin navbar.

### 9. `GET /api/v1/ai/provider/{provider}/models`
*Provider Models*

**Auth:** Bearer JWT (any authenticated user)

**Response `200`:** array of objects —
```json
[
  {}
]
```

**Frontend:** Drill-down list of models for one provider.

### 10. `GET /api/v1/ai/providers`
*List Providers*

**Auth:** Bearer JWT (any authenticated user)

**Response `200`:** array of objects —

| Field | Type | Required |
|-------|------|----------|
| `provider` | str | yes |
| `supported_models` | list[str] | yes |
| `capabilities` | object | yes |
```json
[
  {
    "provider": "<string>",
    "supported_models": [
      "<str>"
    ],
    "capabilities": "{}"
  }
]
```

**Frontend:** Provider grid with supported models + status badges.

---

## 2. Simple Chat

### 11. `POST /chat`
*Chat*

**Auth:** Bearer JWT (any authenticated user)

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `message` | str | yes |  |
```json
{
  "message": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `response` | str | yes |
```json
{
  "response": "<string>"
}
```

**Frontend:** Minimal embedded chat widget (floating button + bottom sheet, no model selection).

---

## 3. Recommendations

### 12. `POST /api/v1/recommendations/bundle-suggestion`
*AI-powered bundle suggestion with budget awareness*

**Auth:** Bearer JWT (any authenticated user)

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `message` | str | yes | User's bundle request (e.g., 'I have $300 and want a monitor') |
| `store_id` | str | yes | Store ID |
| `customer_id` | str | None | no | Optional customer ID |
```json
{
  "message": "<string>",
  "store_id": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `query` | str | yes |
| `store_id` | str | yes |
| `customer_id` | str | None | no |
| `budget` | float | no |
| `bundles` | list[BundleCandidate] | no |
| `promo_code` | str | None | no |
| `rationale` | str | None | no |
| `latency_ms` | float | no |
```json
{
  "query": "<string>",
  "store_id": "<string>"
}
```

**Frontend:** Bundle builder screen: budget-aware suggestion with product groups, prices, promo code.

### 13. `POST /api/v1/recommendations/chat`
*AI-powered product recommendation with spec matching*

**Auth:** Bearer JWT (any authenticated user)

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `message` | str | yes | User's product recommendation query |
| `store_id` | str | yes | Store ID to search in |
| `customer_id` | str | None | no | Optional customer ID |
```json
{
  "message": "<string>",
  "store_id": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `query` | str | yes |
| `store_id` | str | yes |
| `customer_id` | str | None | no |
| `products` | list[ProductCard] | no |
| `rationale` | str | None | no |
| `total_count` | int | no |
| `latency_ms` | float | no |
```json
{
  "query": "<string>",
  "store_id": "<string>"
}
```

**Frontend:** Personalized product recommendations: chat-like input, render product cards from `items`.

---

## 4. Knowledge Base

### 14. `POST /api/v1/knowledge-base/chunk`
*Generate chunks for a processed document*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `document_id` | str | yes |  |
| `strategy` | str | no |  |
| `chunk_size` | int | no |  |
| `overlap` | int | no |  |
| `store_id` | str | None | no |  |
| `organization_id` | str | None | no |  |
| `triggered_by` | str | None | no |  |
```json
{
  "document_id": "<string>"
}
```

**Frontend:** Split a document into chunks (admin pipeline step).

### 15. `GET /api/v1/knowledge-base/documents`
*List knowledge documents*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[KnowledgeDocumentResponse] | yes |
| `total` | int | yes |
| `page` | int | yes |
| `page_size` | int | yes |
```json
{
  "items": [
    {
      "id": "<string>",
      "store_id": "<string>",
      "title": "<string>",
      "description": "<string>",
      "source_url": "<string>",
      "status": "<string>",
      "language": "<string>",
      "metadata": {
        "source_type": "<string>",
        "source_uri": "<string>",
        "mime_type": "<string>",
        "language": "<string>",
        "category": "<string>",
        "tags": [
          "<str>"
        ],
        "attributes": "{}"
      },
      "versions": [
        {
          "version_number": 0,
          "checksum": "<string>",
          "
```

**Frontend:** Documents list screen: table with pagination + search.

### 16. `GET /api/v1/knowledge-base/documents/{document_id}`
*Get a single knowledge document by ID*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `title` | str | yes |
| `description` | str | None | no |
| `source_url` | str | None | no |
| `status` | str | yes |
| `language` | str | yes |
| `metadata` | DocumentMetadata | yes |
| `versions` | list[DocumentVersion] | yes |
| `current_version` | int | yes |
| `chunks` | list[KnowledgeChunkResponse] | no |
| `chunking_strategy` | str | yes |
| `processed_text` | str | None | no |
| `page_count` | int | None | no |
| `word_count` | int | None | no |
| `char_count` | int | None | no |
| `estimated_tokens` | int | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
| `deleted_at` | str | None | no |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "title": "<string>",
  "status": "<string>",
  "language": "<string>",
  "metadata": {
    "source_type": "<string>",
    "source_uri": "<string>",
    "mime_type": "<string>",
    "language": "<string>",
    "category": "<string>",
    "tags": [
      "<str>"
    ],
    "attributes": "{}"
  },
  "versions": [
    {
      "version_number": 0,
      "checksum": "<string>",
      "created_by": "<string>",
      "notes": "<string>",
      "is_current": true,
      "created_at": "<string>"
    }
  ],
  "current_version": 0,
  "chunking_strategy": "
```

**Frontend:** Document detail: metadata, chunk count, actions (delete).

### 17. `DELETE /api/v1/knowledge-base/documents/{document_id}`
*Delete a knowledge document*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `success` | bool | yes |
```json
{
  "success": true
}
```

**Frontend:** Delete button with confirmation dialog.

### 18. `POST /api/v1/knowledge-base/embed`
*Generate embeddings for a document's chunks*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `document_id` | str | yes | Embed all chunks of this document |
| `model` | str | no |  |
| `sync_to_vector_store` | bool | no | Sync vectors to Qdrant after embedding |
| `collection_name` | str | no |  |
| `store_id` | str | None | no |  |
| `organization_id` | str | None | no |  |
| `triggered_by` | str | None | no |  |
```json
{
  "document_id": "<string>"
}
```

**Frontend:** Generate embeddings for chunks (admin pipeline step).

### 19. `GET /api/v1/knowledge-base/jobs/{job_id}`
*Get the status of an async knowledge job*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `job_type` | str | yes |
| `status` | str | yes |
| `progress` | float | yes |
| `payload` | object | yes |
| `result` | object | None | no |
| `error_message` | str | None | no |
| `retry_count` | int | yes |
| `max_retries` | int | yes |
| `store_id` | str | None | no |
| `organization_id` | str | None | no |
| `triggered_by` | str | None | no |
| `celery_task_id` | str | None | no |
| `started_at` | str | None | no |
| `completed_at` | str | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "job_type": "<string>",
  "status": "<string>",
  "progress": 0.0,
  "payload": "{}",
  "retry_count": 0,
  "max_retries": 0,
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Job progress indicator: poll every 2-3s while a pipeline runs.

### 20. `POST /api/v1/knowledge-base/process`
*Process a document (extract + normalize) asynchronously*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `document_id` | str | yes | ID of the uploaded document to process |
| `file_path` | str | yes | Path to the document file |
| `mime_type` | str | None | no |  |
| `also_chunk` | bool | no | Automatically chunk after processing |
| `strategy` | str | no |  |
| `chunk_size` | int | no |  |
| `overlap` | int | no |  |
| `store_id` | str | None | no |  |
| `organization_id` | str | None | no |  |
| `triggered_by` | str | None | no |  |
```json
{
  "document_id": "<string>",
  "file_path": "<string>"
}
```

**Frontend:** Document processing pipeline: submit a document id; show job progress via `GET /jobs/{job_id}` polling.

### 21. `POST /api/v1/knowledge-base/search`
*Semantic search over knowledge base chunks*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `query` | str | yes | Search query text |
| `top_k` | int | no |  |
| `score_threshold` | float | no |  |
| `use_hybrid` | bool | no | Enable hybrid keyword+vector search |
| `use_mmr` | bool | no | Enable MMR diversity |
| `mmr_lambda` | float | no |  |
| `rerank` | bool | no | Enable LLM cross-encoder re-ranking |
| `rerank_top_k` | int | no |  |
| `embedding_model` | str | no |  |
| `organization_id` | str | None | no |  |
| `store_id` | str | None | no |  |
| `language` | str | None | no |  |
| `document_type` | str | None | no |  |
| `knowledge_scope` | str | None | no |  |
| `business_version` | int | None | no |  |
```json
{
  "query": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `query` | str | yes |
| `results` | list[RetrievedChunk] | yes |
| `total_count` | int | yes |
| `strategy` | str | yes |
| `latency_ms` | float | yes |
| `filters_applied` | object | no |
```json
{
  "query": "<string>",
  "results": [
    {
      "chunk_id": "<string>",
      "document_id": "<string>",
      "document_title": "<string>",
      "chunk_index": 0,
      "content": "<string>",
      "score": 0.0,
      "rank": 0,
      "metadata": "{}",
      "language": "<string>",
      "source_type": "<string>"
    }
  ],
  "total_count": 0,
  "strategy": "<string>",
  "latency_ms": 0.0
}
```

**Frontend:** Knowledge search box (RAG): render results with relevance + source snippets.

### 22. `POST /api/v1/knowledge-base/search/hybrid`
*Hybrid search (vector + keyword) over knowledge base chunks*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `query` | str | yes | Search query text |
| `top_k` | int | no |  |
| `score_threshold` | float | no |  |
| `use_hybrid` | bool | no | Enable hybrid keyword+vector search |
| `use_mmr` | bool | no | Enable MMR diversity |
| `mmr_lambda` | float | no |  |
| `rerank` | bool | no | Enable LLM cross-encoder re-ranking |
| `rerank_top_k` | int | no |  |
| `embedding_model` | str | no |  |
| `organization_id` | str | None | no |  |
| `store_id` | str | None | no |  |
| `language` | str | None | no |  |
| `document_type` | str | None | no |  |
| `knowledge_scope` | str | None | no |  |
| `business_version` | int | None | no |  |
```json
{
  "query": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `query` | str | yes |
| `results` | list[RetrievedChunk] | yes |
| `total_count` | int | yes |
| `strategy` | str | yes |
| `latency_ms` | float | yes |
| `filters_applied` | object | no |
```json
{
  "query": "<string>",
  "results": [
    {
      "chunk_id": "<string>",
      "document_id": "<string>",
      "document_title": "<string>",
      "chunk_index": 0,
      "content": "<string>",
      "score": 0.0,
      "rank": 0,
      "metadata": "{}",
      "language": "<string>",
      "source_type": "<string>"
    }
  ],
  "total_count": 0,
  "strategy": "<string>",
  "latency_ms": 0.0
}
```

**Frontend:** Advanced search tab: combine vector + keyword results with per-hit scores.

### 23. `POST /api/v1/knowledge-base/summaries/generate`
*Generate Business Summary*

**Auth:** Bearer JWT + `admin` role

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `document_id` | str | yes |
| `version_number` | int | yes |
| `title` | str | yes |
| `summary` | str | yes |
| `metadata` | object | yes |
| `sections` | object | no |
| `document_count` | int | no |
| `model` | str | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "document_id": "<string>",
  "version_number": 0,
  "title": "<string>",
  "summary": "<string>",
  "metadata": "{}",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Business summary generator: form + loading state, show summary cards.

### 24. `GET /api/v1/knowledge-base/summaries/history`
*List Business Summary History*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[BusinessSummaryGenerationResponse] | yes |
| `total` | int | yes |
| `page` | int | yes |
| `page_size` | int | yes |
```json
{
  "items": [
    {
      "id": "<string>",
      "document_id": "<string>",
      "version_number": 0,
      "title": "<string>",
      "summary": "<string>",
      "metadata": "{}",
      "sections": "{}",
      "document_count": 0,
      "model": "<string>",
      "created_at": "<string>",
      "updated_at": "<string>"
    }
  ],
  "total": 0,
  "page": 0,
  "page_size": 0
}
```

**Frontend:** Summaries history list with pagination.

### 25. `POST /api/v1/knowledge-base/summaries/regenerate`
*Regenerate Business Summary*

**Auth:** Bearer JWT + `admin` role

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `document_id` | str | yes |
| `version_number` | int | yes |
| `title` | str | yes |
| `summary` | str | yes |
| `metadata` | object | yes |
| `sections` | object | no |
| `document_count` | int | no |
| `model` | str | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "document_id": "<string>",
  "version_number": 0,
  "title": "<string>",
  "summary": "<string>",
  "metadata": "{}",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Regenerate button on an existing summary card.

### 26. `POST /api/v1/knowledge-base/summary`
*Generate a business summary for a store*

**Auth:** Bearer JWT + `admin` role

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `document_id` | str | yes |
| `version_number` | int | yes |
| `title` | str | yes |
| `summary` | str | yes |
| `metadata` | object | yes |
| `sections` | object | no |
| `document_count` | int | no |
| `model` | str | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "document_id": "<string>",
  "version_number": 0,
  "title": "<string>",
  "summary": "<string>",
  "metadata": "{}",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Legacy single summary generation (use `/summaries/generate` in new code).

### 27. `POST /api/v1/knowledge-base/summary/regenerate`
*Regenerate the business summary for a store*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `document_id` | str | yes |
| `version_number` | int | yes |
| `title` | str | yes |
| `summary` | str | yes |
| `metadata` | object | yes |
| `sections` | object | no |
| `document_count` | int | no |
| `model` | str | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "document_id": "<string>",
  "version_number": 0,
  "title": "<string>",
  "summary": "<string>",
  "metadata": "{}",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Legacy regenerate (use `/summaries/regenerate` in new code).

### 28. `POST /api/v1/knowledge-base/upload`
*Upload a document to the knowledge base*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | str | yes |  |
```json
{
  "file": "<string>"
}
```

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `original_filename` | str | yes |
| `stored_filename` | str | yes |
| `file_path` | str | yes |
| `file_size` | int | yes |
| `mime_type` | str | yes |
| `extension` | str | yes |
| `checksum` | str | yes |
| `content_type` | str | yes |
| `uploaded_by` | str | yes |
| `organization_id` | str | yes |
| `store_id` | str | yes |
| `knowledge_scope` | str | yes |
| `status` | str | yes |
| `document_metadata` | DocumentMetadata | yes |
| `virus_scan_status` | str | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
| `deleted_at` | str | None | no |
```json
{
  "id": "<string>",
  "original_filename": "<string>",
  "stored_filename": "<string>",
  "file_path": "<string>",
  "file_size": 0,
  "mime_type": "<string>",
  "extension": "<string>",
  "checksum": "<string>",
  "content_type": "<string>",
  "uploaded_by": "<string>",
  "organization_id": "<string>",
  "store_id": "<string>",
  "knowledge_scope": "<string>",
  "status": "<string>"
}
```

**Frontend:** Admin 'Upload document' modal: file picker + store selector; show upload progress + created doc.

---

## 5. Commerce

### 29. `GET /api/v1/commerce/categories`
*List Categories*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[None] | yes |
| `total` | int | yes |
| `page` | int | yes |
| `page_size` | int | yes |
```json
{
  "items": [
    "<item>"
  ],
  "total": 0,
  "page": 0,
  "page_size": 0
}
```

**Frontend:** Category tree/list screen.

### 30. `POST /api/v1/commerce/categories`
*Create Category*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `store_id` | str | yes |  |
| `org_id` | str | yes |  |
| `external_id` | str | None | no |  |
| `name` | str | yes |  |
| `description` | str | None | no |  |
| `handle` | str | None | no |  |
| `parent_id` | str | None | no |  |
| `image_url` | str | None | no |  |
| `sort_order` | int | no |  |
| `product_count` | int | no |  |
```json
{
  "store_id": "<string>",
  "org_id": "<string>",
  "name": "<string>"
}
```

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `name` | str | yes |
| `description` | str | None | no |
| `handle` | str | None | no |
| `parent_id` | str | None | no |
| `image_url` | str | None | no |
| `sort_order` | int | yes |
| `product_count` | int | yes |
| `audit` | AuditInfo | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>",
  "name": "<string>",
  "sort_order": 0,
  "product_count": 0,
  "audit": {
    "created_at": "<string>",
    "updated_at": "<string>",
    "updated_by": "<string>"
  },
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** 'Add category' form.

### 31. `GET /api/v1/commerce/categories/root`
*Get Root Categories*

**Auth:** Bearer JWT + `admin` role

**Response `200`:** array of objects —

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `name` | str | yes |
| `description` | str | None | no |
| `handle` | str | None | no |
| `parent_id` | str | None | no |
| `image_url` | str | None | no |
| `sort_order` | int | yes |
| `product_count` | int | yes |
| `audit` | AuditInfo | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
[
  {
    "id": "<string>",
    "store_id": "<string>",
    "org_id": "<string>",
    "name": "<string>",
    "sort_order": 0,
    "product_count": 0,
    "audit": {
      "created_at": "<string>",
      "updated_at": "<string>",
      "updated_by": "<string>"
    },
    "created_at": "<string>",
    "updated_at": "<string>"
  }
]
```

### 32. `GET /api/v1/commerce/categories/{category_id}`
*Get Category*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `name` | str | yes |
| `description` | str | None | no |
| `handle` | str | None | no |
| `parent_id` | str | None | no |
| `image_url` | str | None | no |
| `sort_order` | int | yes |
| `product_count` | int | yes |
| `audit` | AuditInfo | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>",
  "name": "<string>",
  "sort_order": 0,
  "product_count": 0,
  "audit": {
    "created_at": "<string>",
    "updated_at": "<string>",
    "updated_by": "<string>"
  },
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Category detail.

### 33. `PUT /api/v1/commerce/categories/{category_id}`
*Update Category*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | str | None | no |  |
| `description` | str | None | no |  |
| `handle` | str | None | no |  |
| `parent_id` | str | None | no |  |
| `image_url` | str | None | no |  |
| `sort_order` | int | None | no |  |
| `product_count` | int | None | no |  |
```json
{}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `name` | str | yes |
| `description` | str | None | no |
| `handle` | str | None | no |
| `parent_id` | str | None | no |
| `image_url` | str | None | no |
| `sort_order` | int | yes |
| `product_count` | int | yes |
| `audit` | AuditInfo | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>",
  "name": "<string>",
  "sort_order": 0,
  "product_count": 0,
  "audit": {
    "created_at": "<string>",
    "updated_at": "<string>",
    "updated_by": "<string>"
  },
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** 'Edit category' form.

### 34. `DELETE /api/v1/commerce/categories/{category_id}`
*Delete Category*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `success` | bool | yes |
```json
{
  "success": true
}
```

**Frontend:** Delete category (confirm dialog).

### 35. `GET /api/v1/commerce/categories/{category_id}/children`
*Get Category Children*

**Auth:** Bearer JWT + `admin` role

**Response `200`:** array of objects —

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `name` | str | yes |
| `description` | str | None | no |
| `handle` | str | None | no |
| `parent_id` | str | None | no |
| `image_url` | str | None | no |
| `sort_order` | int | yes |
| `product_count` | int | yes |
| `audit` | AuditInfo | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
[
  {
    "id": "<string>",
    "store_id": "<string>",
    "org_id": "<string>",
    "name": "<string>",
    "sort_order": 0,
    "product_count": 0,
    "audit": {
      "created_at": "<string>",
      "updated_at": "<string>",
      "updated_by": "<string>"
    },
    "created_at": "<string>",
    "updated_at": "<string>"
  }
]
```

**Frontend:** Expand a node in the category tree.

### 36. `GET /api/v1/commerce/inventory`
*List Inventory*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[None] | yes |
| `total` | int | yes |
| `page` | int | yes |
| `page_size` | int | yes |
```json
{
  "items": [
    "<item>"
  ],
  "total": 0,
  "page": 0,
  "page_size": 0
}
```

**Frontend:** Inventory list with stock levels + low-stock highlight.

### 37. `POST /api/v1/commerce/inventory`
*Create Inventory*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `product_id` | str | yes |  |
| `variant_id` | str | yes |  |
| `store_id` | str | yes |  |
| `org_id` | str | yes |  |
| `external_id` | str | None | no |  |
| `quantity` | int | no |  |
| `available` | int | no |  |
| `committed` | int | no |  |
| `incoming` | int | no |  |
| `location_id` | str | None | no |  |
| `location_name` | str | None | no |  |
| `low_stock_threshold` | int | None | no |  |
```json
{
  "product_id": "<string>",
  "variant_id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>"
}
```

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `product_id` | str | yes |
| `variant_id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `quantity` | int | yes |
| `available` | int | yes |
| `committed` | int | yes |
| `incoming` | int | yes |
| `location_id` | str | None | no |
| `location_name` | str | None | no |
| `low_stock_threshold` | int | None | no |
| `audit` | AuditInfo | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "product_id": "<string>",
  "variant_id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>",
  "quantity": 0,
  "available": 0,
  "committed": 0,
  "incoming": 0,
  "audit": {
    "created_at": "<string>",
    "updated_at": "<string>",
    "updated_by": "<string>"
  },
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Add inventory record form.

### 38. `GET /api/v1/commerce/inventory/low-stock`
*Get Low Stock Inventory*

**Auth:** Bearer JWT + `admin` role

**Response `200`:** array of objects —

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `product_id` | str | yes |
| `variant_id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `quantity` | int | yes |
| `available` | int | yes |
| `committed` | int | yes |
| `incoming` | int | yes |
| `location_id` | str | None | no |
| `location_name` | str | None | no |
| `low_stock_threshold` | int | None | no |
| `audit` | AuditInfo | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
[
  {
    "id": "<string>",
    "product_id": "<string>",
    "variant_id": "<string>",
    "store_id": "<string>",
    "org_id": "<string>",
    "quantity": 0,
    "available": 0,
    "committed": 0,
    "incoming": 0,
    "audit": {
      "created_at": "<string>",
      "updated_at": "<string>",
      "updated_by": "<string>"
    },
    "created_at": "<string>",
    "updated_at": "<string>"
  }
]
```

**Frontend:** Low-stock alert widget (dashboard).

### 39. `GET /api/v1/commerce/inventory/{variant_id}`
*Get Inventory*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `product_id` | str | yes |
| `variant_id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `quantity` | int | yes |
| `available` | int | yes |
| `committed` | int | yes |
| `incoming` | int | yes |
| `location_id` | str | None | no |
| `location_name` | str | None | no |
| `low_stock_threshold` | int | None | no |
| `audit` | AuditInfo | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "product_id": "<string>",
  "variant_id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>",
  "quantity": 0,
  "available": 0,
  "committed": 0,
  "incoming": 0,
  "audit": {
    "created_at": "<string>",
    "updated_at": "<string>",
    "updated_by": "<string>"
  },
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Inventory detail per variant.

### 40. `PUT /api/v1/commerce/inventory/{variant_id}`
*Update Inventory*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `quantity` | int | None | no |  |
| `available` | int | None | no |  |
| `committed` | int | None | no |  |
| `incoming` | int | None | no |  |
| `location_id` | str | None | no |  |
| `location_name` | str | None | no |  |
| `low_stock_threshold` | int | None | no |  |
```json
{}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `product_id` | str | yes |
| `variant_id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `quantity` | int | yes |
| `available` | int | yes |
| `committed` | int | yes |
| `incoming` | int | yes |
| `location_id` | str | None | no |
| `location_name` | str | None | no |
| `low_stock_threshold` | int | None | no |
| `audit` | AuditInfo | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "product_id": "<string>",
  "variant_id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>",
  "quantity": 0,
  "available": 0,
  "committed": 0,
  "incoming": 0,
  "audit": {
    "created_at": "<string>",
    "updated_at": "<string>",
    "updated_by": "<string>"
  },
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Edit stock quantity inline.

### 41. `GET /api/v1/commerce/orders`
*List Orders*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[None] | yes |
| `total` | int | yes |
| `page` | int | yes |
| `page_size` | int | yes |
```json
{
  "items": [
    "<item>"
  ],
  "total": 0,
  "page": 0,
  "page_size": 0
}
```

**Frontend:** Orders list: table with pagination.

### 42. `POST /api/v1/commerce/orders`
*Create Order*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `store_id` | str | yes |  |
| `org_id` | str | yes |  |
| `external_id` | str | None | no |  |
| `customer_id` | str | None | no |  |
| `customer_email` | str | None | no |  |
| `financial_status` | str | no |  |
| `fulfillment_status` | str | None | no |  |
| `currency` | str | no |  |
| `notes` | str | None | no |  |
| `tags` | list[str] | no |  |
| `metadata` | object | no |  |
```json
{
  "store_id": "<string>",
  "org_id": "<string>"
}
```

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `customer_id` | str | None | no |
| `customer_email` | str | None | no |
| `line_items` | list[None] | no |
| `financial_status` | str | yes |
| `fulfillment_status` | str | None | no |
| `currency` | str | yes |
| `notes` | str | None | no |
| `tags` | list[str] | yes |
| `cancelled_at` | str | None | no |
| `audit` | AuditInfo | yes |
| `metadata` | object | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>",
  "financial_status": "<string>",
  "currency": "<string>",
  "tags": [
    "<str>"
  ],
  "audit": {
    "created_at": "<string>",
    "updated_at": "<string>",
    "updated_by": "<string>"
  },
  "metadata": "{}",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

### 43. `GET /api/v1/commerce/orders/{order_id}`
*Get Order*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `customer_id` | str | None | no |
| `customer_email` | str | None | no |
| `line_items` | list[None] | no |
| `financial_status` | str | yes |
| `fulfillment_status` | str | None | no |
| `currency` | str | yes |
| `notes` | str | None | no |
| `tags` | list[str] | yes |
| `cancelled_at` | str | None | no |
| `audit` | AuditInfo | yes |
| `metadata` | object | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>",
  "financial_status": "<string>",
  "currency": "<string>",
  "tags": [
    "<str>"
  ],
  "audit": {
    "created_at": "<string>",
    "updated_at": "<string>",
    "updated_by": "<string>"
  },
  "metadata": "{}",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Order detail page (line items, totals).

### 44. `PUT /api/v1/commerce/orders/{order_id}/status`
*Update Order Status*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `financial_status` | str | None | no |  |
| `fulfillment_status` | str | None | no |  |
| `notes` | str | None | no |  |
| `tags` | list[str] | None | no |  |
```json
{}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `org_id` | str | yes |
| `external_id` | str | None | no |
| `customer_id` | str | None | no |
| `customer_email` | str | None | no |
| `line_items` | list[None] | no |
| `financial_status` | str | yes |
| `fulfillment_status` | str | None | no |
| `currency` | str | yes |
| `notes` | str | None | no |
| `tags` | list[str] | yes |
| `cancelled_at` | str | None | no |
| `audit` | AuditInfo | yes |
| `metadata` | object | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "org_id": "<string>",
  "financial_status": "<string>",
  "currency": "<string>",
  "tags": [
    "<str>"
  ],
  "audit": {
    "created_at": "<string>",
    "updated_at": "<string>",
    "updated_by": "<string>"
  },
  "metadata": "{}",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Order status dropdown/action.

### 45. `GET /api/v1/commerce/products`
*List Products*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[None] | yes |
| `total` | int | yes |
| `page` | int | yes |
| `page_size` | int | yes |
```json
{
  "items": [
    "<item>"
  ],
  "total": 0,
  "page": 0,
  "page_size": 0
}
```

**Frontend:** Product catalog list: cards/table with filters + pagination.

### 46. `POST /api/v1/commerce/products`
*Create Product*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `store_id` | str | yes |  |
| `organization_id` | str | yes |  |
| `external_id` | str | None | no |  |
| `title` | str | yes |  |
| `description` | str | None | no |  |
| `handle` | str | None | no |  |
| `status` | str | no |  |
| `product_type` | str | None | no |  |
| `vendor` | str | None | no |  |
| `tags` | list[str] | no |  |
| `images` | list[Image] | no |  |
| `variants` | list[VariantCreate] | no |  |
| `options` | list[ProductOption] | no |  |
| `seo` | SEO | no |  |
| `category_id` | str | None | no |  |
| `metadata` | object | no |  |
```json
{
  "store_id": "<string>",
  "organization_id": "<string>",
  "title": "<string>"
}
```

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `organization_id` | str | yes |
| `external_id` | str | None | no |
| `title` | str | yes |
| `description` | str | None | no |
| `handle` | str | None | no |
| `status` | str | yes |
| `product_type` | str | None | no |
| `vendor` | str | None | no |
| `tags` | list[str] | yes |
| `images` | list[Image] | yes |
| `variants` | list[VariantResponse] | yes |
| `options` | list[ProductOptionResponse] | yes |
| `seo` | SEO | yes |
| `category_id` | str | None | no |
| `audit` | AuditInfo | yes |
| `metadata` | object | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "organization_id": "<string>",
  "title": "<string>",
  "status": "<string>",
  "tags": [
    "<str>"
  ],
  "images": [
    {
      "url": "<string>",
      "alt_text": "<string>",
      "width": 0,
      "height": 0,
      "position": 0
    }
  ],
  "variants": [
    {
      "id": "<string>",
      "sku": "<string>",
      "title": "<string>",
      "price": {
        "amount": "<string>",
        "currency": "<string>"
      },
      "compare_at_price": {
        "amount": "<string>",
        "currency": "<string>"
      },
      "inventory_
```

**Frontend:** 'Add product' form (admin catalog).

### 47. `GET /api/v1/commerce/products/{product_id}`
*Get Product*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `organization_id` | str | yes |
| `external_id` | str | None | no |
| `title` | str | yes |
| `description` | str | None | no |
| `handle` | str | None | no |
| `status` | str | yes |
| `product_type` | str | None | no |
| `vendor` | str | None | no |
| `tags` | list[str] | yes |
| `images` | list[Image] | yes |
| `variants` | list[VariantResponse] | yes |
| `options` | list[ProductOptionResponse] | yes |
| `seo` | SEO | yes |
| `category_id` | str | None | no |
| `audit` | AuditInfo | yes |
| `metadata` | object | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "organization_id": "<string>",
  "title": "<string>",
  "status": "<string>",
  "tags": [
    "<str>"
  ],
  "images": [
    {
      "url": "<string>",
      "alt_text": "<string>",
      "width": 0,
      "height": 0,
      "position": 0
    }
  ],
  "variants": [
    {
      "id": "<string>",
      "sku": "<string>",
      "title": "<string>",
      "price": {
        "amount": "<string>",
        "currency": "<string>"
      },
      "compare_at_price": {
        "amount": "<string>",
        "currency": "<string>"
      },
      "inventory_
```

**Frontend:** Product detail page.

### 48. `PUT /api/v1/commerce/products/{product_id}`
*Update Product*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `title` | str | None | no |  |
| `description` | str | None | no |  |
| `handle` | str | None | no |  |
| `status` | str | None | no |  |
| `product_type` | str | None | no |  |
| `vendor` | str | None | no |  |
| `tags` | list[str] | None | no |  |
| `images` | list[Image] | None | no |  |
| `variants` | list[VariantCreate] | None | no |  |
| `options` | list[ProductOption] | None | no |  |
| `seo` | SEO | None | no |  |
| `category_id` | str | None | no |  |
| `metadata` | object | None | no |  |
```json
{}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `organization_id` | str | yes |
| `external_id` | str | None | no |
| `title` | str | yes |
| `description` | str | None | no |
| `handle` | str | None | no |
| `status` | str | yes |
| `product_type` | str | None | no |
| `vendor` | str | None | no |
| `tags` | list[str] | yes |
| `images` | list[Image] | yes |
| `variants` | list[VariantResponse] | yes |
| `options` | list[ProductOptionResponse] | yes |
| `seo` | SEO | yes |
| `category_id` | str | None | no |
| `audit` | AuditInfo | yes |
| `metadata` | object | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "organization_id": "<string>",
  "title": "<string>",
  "status": "<string>",
  "tags": [
    "<str>"
  ],
  "images": [
    {
      "url": "<string>",
      "alt_text": "<string>",
      "width": 0,
      "height": 0,
      "position": 0
    }
  ],
  "variants": [
    {
      "id": "<string>",
      "sku": "<string>",
      "title": "<string>",
      "price": {
        "amount": "<string>",
        "currency": "<string>"
      },
      "compare_at_price": {
        "amount": "<string>",
        "currency": "<string>"
      },
      "inventory_
```

**Frontend:** 'Edit product' form; PUT with partial fields.

### 49. `DELETE /api/v1/commerce/products/{product_id}`
*Delete Product*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `success` | bool | yes |
```json
{
  "success": true
}
```

**Frontend:** Delete product (confirm dialog).

---

## 6. Tickets

### 50. `GET /api/v1/tickets`
*List Tickets*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[TicketResponse] | yes |
| `total` | int | yes |
| `page` | int | yes |
| `page_size` | int | yes |
```json
{
  "items": [
    {
      "id": "<string>",
      "ticket_id": "<string>",
      "store_id": "<string>",
      "customer_id": "<string>",
      "sentiment": "<string>",
      "category": "<string>",
      "summary": "<string>",
      "priority": "<string>",
      "status": "<string>",
      "suggested_response": "<string>",
      "resolution_type": "<string>",
      "analyzed_at": "<string>",
      "created_at": "<string>",
      "updated_at": "<string>"
    }
  ],
  "total": 0,
  "page": 0,
  "page_size": 0
}
```

**Frontend:** Tickets list: filters (status/priority/sentiment), badges, pagination.

### 51. `POST /api/v1/tickets`
*Create Ticket*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `store_id` | str | yes |  |
| `customer_id` | str | yes |  |
| `conversation_id` | str | None | no |  |
| `messages` | list[str] | no |  |
```json
{
  "store_id": "<string>",
  "customer_id": "<string>"
}
```

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `ticket_id` | str | yes |
| `store_id` | str | yes |
| `customer_id` | str | yes |
| `sentiment` | str | yes |
| `category` | str | yes |
| `summary` | str | yes |
| `priority` | str | yes |
| `status` | str | yes |
| `suggested_response` | str | yes |
| `resolution_type` | str | no |
| `analyzed_at` | str | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
| `customer` | CustomerProfile | None | no |
| `recent_orders` | list[Order] | no |
| `conversation` | ConversationSummary | None | no |
| `messages` | list[TicketMessage] | no |
| `assigned_to` | str | None | no |
| `eta` | str | None | no |
```json
{
  "id": "<string>",
  "ticket_id": "<string>",
  "store_id": "<string>",
  "customer_id": "<string>",
  "sentiment": "<string>",
  "category": "<string>",
  "summary": "<string>",
  "priority": "<string>",
  "status": "<string>",
  "suggested_response": "<string>",
  "analyzed_at": "<string>",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Optional manual 'New ticket' form (tickets are normally auto-created by chat).

### 52. `GET /api/v1/tickets/metrics/resolution`
*Get Resolution Metrics*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `store_id` | str | yes |
| `total_tickets` | int | yes |
| `ai_resolved` | int | yes |
| `human_resolved` | int | yes |
| `unresolved` | int | yes |
| `escalated` | int | yes |
| `resolution_rate` | float | yes |
```json
{
  "store_id": "<string>",
  "total_tickets": 0,
  "ai_resolved": 0,
  "human_resolved": 0,
  "unresolved": 0,
  "escalated": 0,
  "resolution_rate": 0.0
}
```

**Frontend:** Dashboard KPI cards + resolution-rate progress bar.

### 53. `GET /api/v1/tickets/{ticket_id}`
*Get Ticket*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `ticket_id` | str | yes |
| `store_id` | str | yes |
| `customer_id` | str | yes |
| `sentiment` | str | yes |
| `category` | str | yes |
| `summary` | str | yes |
| `priority` | str | yes |
| `status` | str | yes |
| `suggested_response` | str | yes |
| `resolution_type` | str | no |
| `analyzed_at` | str | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
| `customer` | CustomerProfile | None | no |
| `recent_orders` | list[Order] | no |
| `conversation` | ConversationSummary | None | no |
| `messages` | list[TicketMessage] | no |
| `assigned_to` | str | None | no |
| `eta` | str | None | no |
```json
{
  "id": "<string>",
  "ticket_id": "<string>",
  "store_id": "<string>",
  "customer_id": "<string>",
  "sentiment": "<string>",
  "category": "<string>",
  "summary": "<string>",
  "priority": "<string>",
  "status": "<string>",
  "suggested_response": "<string>",
  "analyzed_at": "<string>",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Ticket detail: thread, customer card, orders, AI summary + suggested response.

### 54. `DELETE /api/v1/tickets/{ticket_id}`
*Delete Ticket*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `success` | bool | yes |
```json
{
  "success": true
}
```

**Frontend:** Delete ticket (confirm dialog).

### 55. `POST /api/v1/tickets/{ticket_id}/escalate`
*Escalate Ticket*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `priority` | str | None | no |  |
| `assigned_to` | str | None | no |  |
| `eta` | str | None | no |  |
| `message` | str | None | no |  |
```json
{}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `ticket_id` | str | yes |
| `store_id` | str | yes |
| `customer_id` | str | yes |
| `sentiment` | str | yes |
| `category` | str | yes |
| `summary` | str | yes |
| `priority` | str | yes |
| `status` | str | yes |
| `suggested_response` | str | yes |
| `resolution_type` | str | no |
| `analyzed_at` | str | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
| `customer` | CustomerProfile | None | no |
| `recent_orders` | list[Order] | no |
| `conversation` | ConversationSummary | None | no |
| `messages` | list[TicketMessage] | no |
| `assigned_to` | str | None | no |
| `eta` | str | None | no |
```json
{
  "id": "<string>",
  "ticket_id": "<string>",
  "store_id": "<string>",
  "customer_id": "<string>",
  "sentiment": "<string>",
  "category": "<string>",
  "summary": "<string>",
  "priority": "<string>",
  "status": "<string>",
  "suggested_response": "<string>",
  "analyzed_at": "<string>",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** 'Escalate' modal: priority, assignee, ETA, note.

### 56. `POST /api/v1/tickets/{ticket_id}/messages`
*Add Ticket Message*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sender` | str | no |  |
| `content` | str | yes |  |
```json
{
  "content": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `ticket_id` | str | yes |
| `store_id` | str | yes |
| `customer_id` | str | yes |
| `sentiment` | str | yes |
| `category` | str | yes |
| `summary` | str | yes |
| `priority` | str | yes |
| `status` | str | yes |
| `suggested_response` | str | yes |
| `resolution_type` | str | no |
| `analyzed_at` | str | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
| `customer` | CustomerProfile | None | no |
| `recent_orders` | list[Order] | no |
| `conversation` | ConversationSummary | None | no |
| `messages` | list[TicketMessage] | no |
| `assigned_to` | str | None | no |
| `eta` | str | None | no |
```json
{
  "id": "<string>",
  "ticket_id": "<string>",
  "store_id": "<string>",
  "customer_id": "<string>",
  "sentiment": "<string>",
  "category": "<string>",
  "summary": "<string>",
  "priority": "<string>",
  "status": "<string>",
  "suggested_response": "<string>",
  "analyzed_at": "<string>",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Reply composer at the bottom of the thread.

### 57. `GET /api/v1/tickets/{ticket_id}/notifications`
*List Ticket Notifications*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[TicketNotification] | yes |
| `total` | int | yes |
| `unread` | int | yes |
```json
{
  "items": [
    {
      "id": "<string>",
      "ticket_id": "<string>",
      "store_id": "<string>",
      "customer_id": "<string>",
      "message": "<string>",
      "eta": "<string>",
      "read": true,
      "created_at": "<string>"
    }
  ],
  "total": 0,
  "unread": 0
}
```

**Frontend:** Notification bell + list (unread badge).

### 58. `POST /api/v1/tickets/{ticket_id}/resolve`
*Resolve Ticket*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `resolution_type` | str | no |  |
| `message` | str | None | no |  |
```json
{}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `ticket_id` | str | yes |
| `store_id` | str | yes |
| `customer_id` | str | yes |
| `sentiment` | str | yes |
| `category` | str | yes |
| `summary` | str | yes |
| `priority` | str | yes |
| `status` | str | yes |
| `suggested_response` | str | yes |
| `resolution_type` | str | no |
| `analyzed_at` | str | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
| `customer` | CustomerProfile | None | no |
| `recent_orders` | list[Order] | no |
| `conversation` | ConversationSummary | None | no |
| `messages` | list[TicketMessage] | no |
| `assigned_to` | str | None | no |
| `eta` | str | None | no |
```json
{
  "id": "<string>",
  "ticket_id": "<string>",
  "store_id": "<string>",
  "customer_id": "<string>",
  "sentiment": "<string>",
  "category": "<string>",
  "summary": "<string>",
  "priority": "<string>",
  "status": "<string>",
  "suggested_response": "<string>",
  "analyzed_at": "<string>",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** 'Resolve' button + optional note dialog.

### 59. `PATCH /api/v1/tickets/{ticket_id}/status`
*Update Ticket Status*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `status` | str | yes |  |
| `resolution_type` | str | None | no |  |
```json
{
  "status": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `ticket_id` | str | yes |
| `store_id` | str | yes |
| `customer_id` | str | yes |
| `sentiment` | str | yes |
| `category` | str | yes |
| `summary` | str | yes |
| `priority` | str | yes |
| `status` | str | yes |
| `suggested_response` | str | yes |
| `resolution_type` | str | no |
| `analyzed_at` | str | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
| `customer` | CustomerProfile | None | no |
| `recent_orders` | list[Order] | no |
| `conversation` | ConversationSummary | None | no |
| `messages` | list[TicketMessage] | no |
| `assigned_to` | str | None | no |
| `eta` | str | None | no |
```json
{
  "id": "<string>",
  "ticket_id": "<string>",
  "store_id": "<string>",
  "customer_id": "<string>",
  "sentiment": "<string>",
  "category": "<string>",
  "summary": "<string>",
  "priority": "<string>",
  "status": "<string>",
  "suggested_response": "<string>",
  "analyzed_at": "<string>",
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Status dropdown on ticket detail.

---

## 7. Integrations

### 60. `POST /api/v1/integration/agent-sync`
*Agent Sync*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `platform_name` | str | yes | Name of the platform |
| `raw_spec` | None | yes | OpenAPI/Swagger specification |
| `store_id` | str | yes | Store ID for the integration |
| `name` | str | None | no | Optional connection name |
| `credentials` | object | None | no | API credentials (tokens, keys) |
| `auto_sync` | bool | no | Run sync automatically after mapping |
```json
{
  "platform_name": "<string>",
  "raw_spec": "{}",
  "store_id": "<string>"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `connection_id` | str | None | no |
| `mapping_report` | object | None | no |
| `capabilities` | object | None | no |
| `sync_result` | object | None | no |
| `feature_analysis` | FeatureAnalysis | None | no |
| `error` | str | None | no |
| `user_friendly_error` | str | None | no |
| `started_at` | str | yes |
| `completed_at` | str | None | no |
```json
{
  "started_at": "<string>"
}
```

**Frontend:** AI-configured sync job runner (advanced wizard).

### 61. `GET /api/v1/integration/connections`
*List Connections*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[ConnectionResponse] | yes |
| `total` | int | yes |
| `page` | int | yes |
| `page_size` | int | yes |
```json
{
  "items": [
    {
      "id": "<string>",
      "store_id": "<string>",
      "organization_id": "<string>",
      "name": "<string>",
      "platform_name": "<string>",
      "status": "<string>",
      "spec_version": "<string>",
      "auth_config": {
        "type": "<string>",
        "credentials_location": "<string>",
        "scheme": "<string>",
        "name": "<string>",
        "token_url": "<string>",
        "flow": "<string>"
      },
      "entity_mappings": [
        {
          "entity_type": "<string>",
          "list_path": "<string>",
          "list_method": "<string>
```

**Frontend:** Connections list: platform cards with status badges.

### 62. `POST /api/v1/integration/connections`
*Create Connection*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `store_id` | str | yes |  |
| `name` | str | yes |  |
| `platform_name` | str | yes |  |
| `raw_spec` | None | yes | OpenAPI/Swagger specification (JSON dict, YAML string, or raw dict) |
| `auth_config` | AuthConfig | yes |  |
| `credentials` | object | no |  |
| `entity_mappings` | list[EntityMapping] | no |  |
```json
{
  "store_id": "<string>",
  "name": "<string>",
  "platform_name": "<string>",
  "raw_spec": "{}",
  "auth_config": {
    "type": "<string>",
    "credentials_location": "<string>",
    "scheme": "<string>",
    "name": "<string>",
    "token_url": "<string>",
    "flow": "<string>"
  }
}
```

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `organization_id` | str | yes |
| `name` | str | yes |
| `platform_name` | str | yes |
| `status` | str | yes |
| `spec_version` | str | yes |
| `auth_config` | AuthConfig | yes |
| `entity_mappings` | list[EntityMapping] | yes |
| `discovered_endpoints` | list[object] | no |
| `discovered_schemas` | object | no |
| `last_sync_at` | str | None | no |
| `last_sync_status` | str | None | no |
| `last_vector_sync_at` | str | None | no |
| `last_vector_sync_status` | str | None | no |
| `vector_sync_error` | str | None | no |
| `error_message` | str | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "organization_id": "<string>",
  "name": "<string>",
  "platform_name": "<string>",
  "status": "<string>",
  "spec_version": "<string>",
  "auth_config": {
    "type": "<string>",
    "credentials_location": "<string>",
    "scheme": "<string>",
    "name": "<string>",
    "token_url": "<string>",
    "flow": "<string>"
  },
  "entity_mappings": [
    {
      "entity_type": "<string>",
      "list_path": "<string>",
      "list_method": "<string>",
      "detail_path": "<string>",
      "detail_method": "<string>",
      "id_field": "<string>"
```

**Frontend:** 'Connect platform' wizard step 1: platform select + spec upload.

### 63. `GET /api/v1/integration/connections/{connection_id}`
*Get Connection*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `organization_id` | str | yes |
| `name` | str | yes |
| `platform_name` | str | yes |
| `status` | str | yes |
| `spec_version` | str | yes |
| `auth_config` | AuthConfig | yes |
| `entity_mappings` | list[EntityMapping] | yes |
| `discovered_endpoints` | list[object] | no |
| `discovered_schemas` | object | no |
| `last_sync_at` | str | None | no |
| `last_sync_status` | str | None | no |
| `last_vector_sync_at` | str | None | no |
| `last_vector_sync_status` | str | None | no |
| `vector_sync_error` | str | None | no |
| `error_message` | str | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "organization_id": "<string>",
  "name": "<string>",
  "platform_name": "<string>",
  "status": "<string>",
  "spec_version": "<string>",
  "auth_config": {
    "type": "<string>",
    "credentials_location": "<string>",
    "scheme": "<string>",
    "name": "<string>",
    "token_url": "<string>",
    "flow": "<string>"
  },
  "entity_mappings": [
    {
      "entity_type": "<string>",
      "list_path": "<string>",
      "list_method": "<string>",
      "detail_path": "<string>",
      "detail_method": "<string>",
      "id_field": "<string>"
```

**Frontend:** Connection detail: status, mapping summary, actions.

### 64. `DELETE /api/v1/integration/connections/{connection_id}`
*Delete Connection*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `success` | bool | yes |
```json
{
  "success": true
}
```

### 65. `PUT /api/v1/integration/connections/{connection_id}/credentials`
*Update Connection Credentials*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `auth_config` | AuthConfig | yes |  |
| `credentials` | object | yes |  |
```json
{
  "auth_config": {
    "type": "<string>",
    "credentials_location": "<string>",
    "scheme": "<string>",
    "name": "<string>",
    "token_url": "<string>",
    "flow": "<string>"
  },
  "credentials": "{}"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `organization_id` | str | yes |
| `name` | str | yes |
| `platform_name` | str | yes |
| `status` | str | yes |
| `spec_version` | str | yes |
| `auth_config` | AuthConfig | yes |
| `entity_mappings` | list[EntityMapping] | yes |
| `discovered_endpoints` | list[object] | no |
| `discovered_schemas` | object | no |
| `last_sync_at` | str | None | no |
| `last_sync_status` | str | None | no |
| `last_vector_sync_at` | str | None | no |
| `last_vector_sync_status` | str | None | no |
| `vector_sync_error` | str | None | no |
| `error_message` | str | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "organization_id": "<string>",
  "name": "<string>",
  "platform_name": "<string>",
  "status": "<string>",
  "spec_version": "<string>",
  "auth_config": {
    "type": "<string>",
    "credentials_location": "<string>",
    "scheme": "<string>",
    "name": "<string>",
    "token_url": "<string>",
    "flow": "<string>"
  },
  "entity_mappings": [
    {
      "entity_type": "<string>",
      "list_path": "<string>",
      "list_method": "<string>",
      "detail_path": "<string>",
      "detail_method": "<string>",
      "id_field": "<string>"
```

**Frontend:** Credentials form (edit secrets).

### 66. `PUT /api/v1/integration/connections/{connection_id}/mappings`
*Update Connection Mappings*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `entity_mappings` | list[EntityMapping] | yes |  |
```json
{
  "entity_mappings": [
    {
      "entity_type": "<string>",
      "list_path": "<string>",
      "list_method": "<string>",
      "detail_path": "<string>",
      "detail_method": "<string>",
      "id_field": "<string>",
      "pagination": {
        "style": "<string>",
        "page_param": "<string>",
        "limit_param": "<string>",
        "default_limit": 0,
        "cursor_field": "<string>",
        "total_field": "<string>",
        "next_link_field": "<string>"
      },
      "field_mappings": [
        {
          "source": "<string>",
          "target": "<string>",
          "transformer": "<string>",
          "default_value": "{}",
          "required": true
        }
      ]
    }
  ]
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `organization_id` | str | yes |
| `name` | str | yes |
| `platform_name` | str | yes |
| `status` | str | yes |
| `spec_version` | str | yes |
| `auth_config` | AuthConfig | yes |
| `entity_mappings` | list[EntityMapping] | yes |
| `discovered_endpoints` | list[object] | no |
| `discovered_schemas` | object | no |
| `last_sync_at` | str | None | no |
| `last_sync_status` | str | None | no |
| `last_vector_sync_at` | str | None | no |
| `last_vector_sync_status` | str | None | no |
| `vector_sync_error` | str | None | no |
| `error_message` | str | None | no |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "organization_id": "<string>",
  "name": "<string>",
  "platform_name": "<string>",
  "status": "<string>",
  "spec_version": "<string>",
  "auth_config": {
    "type": "<string>",
    "credentials_location": "<string>",
    "scheme": "<string>",
    "name": "<string>",
    "token_url": "<string>",
    "flow": "<string>"
  },
  "entity_mappings": [
    {
      "entity_type": "<string>",
      "list_path": "<string>",
      "list_method": "<string>",
      "detail_path": "<string>",
      "detail_method": "<string>",
      "id_field": "<string>"
```

**Frontend:** Mapping editor: field mapping UI.

### 67. `POST /api/v1/integration/connections/{connection_id}/sync`
*Sync Connection*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `entity_types` | list[str] | None | no |  |
```json
{}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `connection_id` | str | yes |
| `store_id` | str | yes |
| `started_at` | str | yes |
| `completed_at` | str | None | no |
| `status` | str | yes |
| `entity_results` | list[EntitySyncResult] | no |
| `total_duration_seconds` | float | None | no |
| `error` | str | None | no |
```json
{
  "connection_id": "<string>",
  "store_id": "<string>",
  "started_at": "<string>",
  "status": "<string>"
}
```

**Frontend:** 'Sync now' button + progress state.

### 68. `POST /api/v1/integration/schemas/agent-parse`
*Agent Parse Spec*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `platform_name` | str | yes | Name of the platform (e.g., Shopify, WooCommerce) |
| `raw_spec` | None | yes | OpenAPI/Swagger specification (JSON object, YAML string, or raw dict) |
```json
{
  "platform_name": "<string>",
  "raw_spec": "{}"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `platform_name` | str | yes |
| `base_url` | str | yes |
| `api_version` | str | yes |
| `entities` | list[object] | no |
| `feature_analysis` | FeatureAnalysis | no |
| `capabilities` | object | no |
| `warnings` | list[str] | no |
| `errors` | list[str] | no |
| `user_friendly_error` | str | None | no |
```json
{
  "platform_name": "<string>",
  "base_url": "<string>",
  "api_version": "<string>"
}
```

**Frontend:** AI-assisted spec parse (wizard): show parsed + AI-suggested mappings.

### 69. `POST /api/v1/integration/schemas/parse`
*Parse Spec*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `platform_name` | str | yes |  |
| `raw_spec` | None | yes | OpenAPI/Swagger specification (JSON dict, YAML string, or raw dict) |
```json
{
  "platform_name": "<string>",
  "raw_spec": "{}"
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `platform_name` | str | yes |
| `base_url` | str | yes |
| `api_version` | str | yes |
| `endpoints` | list[Endpoint] | yes |
| `schemas` | object | yes |
| `auth_methods` | list[AuthConfig] | yes |
| `discovered_entities` | list[DiscoveredEntity] | no |
| `suggested_mappings` | list[SuggestedMapping] | no |
| `warnings` | list[str] | no |
| `errors` | list[str] | no |
```json
{
  "platform_name": "<string>",
  "base_url": "<string>",
  "api_version": "<string>",
  "endpoints": [
    {
      "path": "<string>",
      "method": "<string>",
      "operation_id": "<string>",
      "summary": "<string>",
      "parameters": [
        "<object>"
      ],
      "response_schema_ref": "<string>"
    }
  ],
  "schemas": "{}",
  "auth_methods": [
    {
      "type": "<string>",
      "credentials_location": "<string>",
      "scheme": "<string>",
      "name": "<string>",
      "token_url": "<string>",
      "flow": "<string>"
    }
  ]
}
```

**Frontend:** Spec parser: upload OpenAPI spec, show parsed endpoints/schemas preview.

---

## 8. Analytics

### 70. `GET /api/v1/analytics/sentiment-summary`
*Get sentiment breakdown for store tickets (admin only)*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `store_id` | str | yes |
| `total` | int | yes |
| `positive_count` | int | yes |
| `neutral_count` | int | yes |
| `negative_count` | int | yes |
| `positive_pct` | float | yes |
| `neutral_pct` | float | yes |
| `negative_pct` | float | yes |
```json
{
  "store_id": "<string>",
  "total": 0,
  "positive_count": 0,
  "neutral_count": 0,
  "negative_count": 0,
  "positive_pct": 0.0,
  "neutral_pct": 0.0,
  "negative_pct": 0.0
}
```

**Frontend:** Sentiment analytics dashboard widget.

---

## 9. Admin Bundle Analytics

### 71. `GET /api/v1/admin/bundles/config`
*Get bundle tracking config for a store*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `threshold` | int | yes |
| `enabled` | bool | yes |
```json
{
  "threshold": 0,
  "enabled": true
}
```

**Frontend:** Bundle tracking settings form (threshold, enabled).

### 72. `PUT /api/v1/admin/bundles/config`
*Update bundle tracking config for a store*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `threshold` | int | None | no |  |
| `enabled` | bool | None | no |  |
```json
{}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `threshold` | int | yes |
| `enabled` | bool | yes |
```json
{
  "threshold": 0,
  "enabled": true
}
```

**Frontend:** Save tracking settings.

### 73. `POST /api/v1/admin/bundles/top/promote`
*Manually promote a bundle to top bundles*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `bundle_key` | str | yes |  |
```json
{
  "bundle_key": "<string>"
}
```

**Response `200`:**
```json
{}
```

**Frontend:** 'Promote to top' button.

### 74. `DELETE /api/v1/admin/bundles/top/{bundle_key}`
*Demote a bundle from top bundles*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**
```json
{}
```

**Frontend:** 'Remove from top' button.

### 75. `POST /api/v1/admin/bundles/track`
*Track a bundle copy event when user copies a promo code*

**Auth:** Bearer JWT + `admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `store_id` | str | yes |  |
| `promo_code` | str | yes |  |
| `product_ids` | list[str] | yes |  |
| `discount_pct` | float | yes |  |
| `total_discount` | float | yes |  |
| `total_original` | float | yes |  |
```json
{
  "store_id": "<string>",
  "promo_code": "<string>",
  "product_ids": [
    "<str>"
  ],
  "discount_pct": 0.0,
  "total_discount": 0.0,
  "total_original": 0.0
}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `bundle_key` | str | yes |
| `copy_count` | int | yes |
| `is_top` | bool | yes |
| `threshold` | int | yes |
```json
{
  "bundle_key": "<string>",
  "copy_count": 0,
  "is_top": true,
  "threshold": 0
}
```

**Frontend:** Promo-copy tracking (analytics event, fire-and-forget).

### 76. `GET /api/v1/admin/bundles/tracking`
*List all tracked bundles with copy counts*

**Auth:** Bearer JWT + `admin` role

**Response `200`:** array of objects —

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `bundle_key` | str | yes |
| `product_ids` | list[str] | yes |
| `discount_pct` | float | yes |
| `total_original` | float | yes |
| `total_discount` | float | yes |
| `promo_code` | str | yes |
| `copy_count` | int | yes |
| `is_top` | bool | yes |
| `promoted_at` | str | None | no |
| `first_copied_at` | str | None | no |
| `last_copied_at` | str | None | no |
```json
[
  {
    "id": "<string>",
    "store_id": "<string>",
    "bundle_key": "<string>",
    "product_ids": [
      "<str>"
    ],
    "discount_pct": 0.0,
    "total_original": 0.0,
    "total_discount": 0.0,
    "promo_code": "<string>",
    "copy_count": 0,
    "is_top": true
  }
]
```

**Frontend:** Top bundles dashboard table.

### 77. `GET /api/v1/admin/bundles/tracking/{bundle_key}`
*Get details of a single tracked bundle*

**Auth:** Bearer JWT + `admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `bundle_key` | str | yes |
| `product_ids` | list[str] | yes |
| `discount_pct` | float | yes |
| `total_original` | float | yes |
| `total_discount` | float | yes |
| `promo_code` | str | yes |
| `copy_count` | int | yes |
| `is_top` | bool | yes |
| `promoted_at` | str | None | no |
| `first_copied_at` | str | None | no |
| `last_copied_at` | str | None | no |
```json
{
  "id": "<string>",
  "store_id": "<string>",
  "bundle_key": "<string>",
  "product_ids": [
    "<str>"
  ],
  "discount_pct": 0.0,
  "total_original": 0.0,
  "total_discount": 0.0,
  "promo_code": "<string>",
  "copy_count": 0,
  "is_top": true
}
```

**Frontend:** Bundle analytics detail.

---

## 10. Admin Prompts

### 78. `GET /api/v1/admin/prompts`
*List Prompts*

**Auth:** Bearer JWT + `super_admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `items` | list[PromptResponse] | yes |
| `total` | int | yes |
| `page` | int | yes |
| `page_size` | int | yes |
```json
{
  "items": [
    {
      "id": "<string>",
      "key": "<string>",
      "type": "<string>",
      "content": "<string>",
      "description": "<string>",
      "tags": [
        "<str>"
      ],
      "version": 0,
      "is_active": true,
      "variables": [
        "<str>"
      ],
      "created_at": "<string>",
      "updated_at": "<string>"
    }
  ],
  "total": 0,
  "page": 0,
  "page_size": 0
}
```

**Frontend:** Prompt management list screen.

### 79. `POST /api/v1/admin/prompts`
*Create Prompt*

**Auth:** Bearer JWT + `super_admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `key` | str | yes |  |
| `type` | str | no |  |
| `content` | str | yes |  |
| `description` | str | no |  |
| `tags` | list[str] | no |  |
| `variables` | list[str] | no |  |
```json
{
  "key": "<string>",
  "content": "<string>"
}
```

**Response `201`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `key` | str | yes |
| `type` | str | yes |
| `content` | str | yes |
| `description` | str | yes |
| `tags` | list[str] | yes |
| `version` | int | yes |
| `is_active` | bool | yes |
| `variables` | list[str] | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "key": "<string>",
  "type": "<string>",
  "content": "<string>",
  "description": "<string>",
  "tags": [
    "<str>"
  ],
  "version": 0,
  "is_active": true,
  "variables": [
    "<str>"
  ],
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Add prompt form.

### 80. `POST /api/v1/admin/prompts/seed`
*Seed Prompts*

**Auth:** Bearer JWT + `super_admin` role

**Response `200`:**
```json
{}
```

**Frontend:** 'Restore defaults' button (danger zone).

### 81. `GET /api/v1/admin/prompts/{key}`
*Get Prompt*

**Auth:** Bearer JWT + `super_admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `key` | str | yes |
| `type` | str | yes |
| `content` | str | yes |
| `description` | str | yes |
| `tags` | list[str] | yes |
| `version` | int | yes |
| `is_active` | bool | yes |
| `variables` | list[str] | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "key": "<string>",
  "type": "<string>",
  "content": "<string>",
  "description": "<string>",
  "tags": [
    "<str>"
  ],
  "version": 0,
  "is_active": true,
  "variables": [
    "<str>"
  ],
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

### 82. `PUT /api/v1/admin/prompts/{key}`
*Update Prompt*

**Auth:** Bearer JWT + `super_admin` role

**Request body**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `content` | str | None | no |  |
| `description` | str | None | no |  |
| `tags` | list[str] | None | no |  |
| `type` | str | None | no |  |
| `variables` | list[str] | None | no |  |
| `is_active` | bool | None | no |  |
```json
{}
```

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `key` | str | yes |
| `type` | str | yes |
| `content` | str | yes |
| `description` | str | yes |
| `tags` | list[str] | yes |
| `version` | int | yes |
| `is_active` | bool | yes |
| `variables` | list[str] | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "key": "<string>",
  "type": "<string>",
  "content": "<string>",
  "description": "<string>",
  "tags": [
    "<str>"
  ],
  "version": 0,
  "is_active": true,
  "variables": [
    "<str>"
  ],
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** Edit prompt form.

### 83. `DELETE /api/v1/admin/prompts/{key}`
*Delete Prompt*

**Auth:** Bearer JWT + `super_admin` role

**Response `204`:** `Successful Response`

**Frontend:** Delete prompt (confirm).

### 84. `POST /api/v1/admin/prompts/{key}/restore`
*Restore Prompt*

**Auth:** Bearer JWT + `super_admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `key` | str | yes |
| `type` | str | yes |
| `content` | str | yes |
| `description` | str | yes |
| `tags` | list[str] | yes |
| `version` | int | yes |
| `is_active` | bool | yes |
| `variables` | list[str] | yes |
| `created_at` | str | yes |
| `updated_at` | str | yes |
```json
{
  "id": "<string>",
  "key": "<string>",
  "type": "<string>",
  "content": "<string>",
  "description": "<string>",
  "tags": [
    "<str>"
  ],
  "version": 0,
  "is_active": true,
  "variables": [
    "<str>"
  ],
  "created_at": "<string>",
  "updated_at": "<string>"
}
```

**Frontend:** 'Restore default' button per prompt.

---

## 11. Admin Analytics

### 85. `GET /api/v1/admin/analytics/sentiment/overview`
*Sentiment Overview*

**Auth:** Bearer JWT + `super_admin` role

**Response `200`:**

| Field | Type | Required |
|-------|------|----------|
| `total` | int | yes |
| `positive_count` | int | yes |
| `neutral_count` | int | yes |
| `negative_count` | int | yes |
| `positive_pct` | float | yes |
| `neutral_pct` | float | yes |
| `negative_pct` | float | yes |
```json
{
  "total": 0,
  "positive_count": 0,
  "neutral_count": 0,
  "negative_count": 0,
  "positive_pct": 0.0,
  "neutral_pct": 0.0,
  "negative_pct": 0.0
}
```

**Frontend:** Admin analytics overview screen.

---

## 12. Auth & Audit

### 86. `GET /api/v1/auth/audit-logs`
*List Audit Logs*

**Auth:** Bearer JWT + `super_admin` role

**Response `200`:** array of objects —

| Field | Type | Required |
|-------|------|----------|
| `id` | str | yes |
| `store_id` | str | yes |
| `user_id` | str | yes |
| `action` | str | yes |
| `resource` | str | yes |
| `outcome` | str | yes |
| `timestamp` | str | yes |
```json
[
  {
    "id": "<string>",
    "store_id": "<string>",
    "user_id": "<string>",
    "action": "<string>",
    "resource": "<string>",
    "outcome": "<string>",
    "timestamp": "<string>"
  }
]
```

**Frontend:** Audit log viewer (super admin): table with filters.

---

## 13. Quick TypeScript pattern

```ts
const API = "https://<api-host>/api/v1";

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}`, ...options.headers },
    ...options,
  });
  if (res.status === 401 || res.status === 403) throw new Error("Not authorized");
  if (res.status === 404) throw new Error("Not found");
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

const list = await api<{ items: unknown[]; total: number }>("/tickets?page=1&page_size=20");
const created = await api<Ticket>("/tickets", { method: "POST", body: JSON.stringify({ ... }) });
```
