# AI Service API Documentation

**Base URL:** `https://aicommerce-ai-service-production.up.railway.app`
**Local Base URL:** `http://localhost:8001`
**Framework:** FastAPI (Python 3.12+)
**Default Provider:** Gemini (`gemini-flash-lite-latest`)
**Supported Providers:** OpenAI, Azure, Gemini, Claude, DeepSeek, Mistral, Ollama

---

## Table of Contents

1. [AI Core (`/api/v1/ai`)](#1-ai-core)
2. [Simple Chat (`/chat`)](#2-simple-chat)
3. [AI-Powered Recommendations (`/api/v1/recommendations`)](#3-ai-powered-recommendations)
4. [RAG Chat (`/rag`)](#4-rag-chat)
5. [Knowledge Base (`/api/v1/knowledge-base`)](#5-knowledge-base)
6. [Knowledge Jobs (`/knowledge/jobs`)](#6-knowledge-jobs)
7. [Knowledge Retrieval (`/knowledge/retrieval`)](#7-knowledge-retrieval)
8. [Integration (AI-Agent) (`/api/v1/integration`)](#8-integration-ai-agent)
9. [Health (`/health`)](#9-health)

---

# 1. AI Core

Core AI orchestration — the central module for all LLM interactions. Routes are under `/api/v1/ai`.

> **Importance:** This is the **brain** of the AI Commerce platform. Every AI feature (chat, streaming, structured output, embeddings, tool calling) goes through this service. It handles auto-fallback between providers, cost tracking, token counting, and performance metrics.

---

## 1.1 Chat Completion

Generate a chat completion with automatic fallback to alternative providers if the primary fails.

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/ai/chat` |

### Request Body

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Hello, who are you?"
    }
  ],
  "model": "gemini-flash-lite-latest",
  "temperature": 0.7,
  "top_p": 0.9,
  "max_tokens": 1024,
  "stream": false,
  "tools": null,
  "tool_choice": null,
  "json_mode": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `messages` | `[Message]` | ✅ | Array of messages (system, user, assistant, tool) |
| `model` | `string` | ✅ | Model identifier from registry |
| `temperature` | `float` | ❌ | Sampling temperature (0.0 — 2.0) |
| `top_p` | `float` | ❌ | Nucleus sampling (0.0 — 1.0) |
| `max_tokens` | `int` | ❌ | Maximum tokens in response |
| `stream` | `bool` | ❌ | Enable streaming (default: false) |
| `tools` | `[Tool]` | ❌ | Tool/function definitions |
| `tool_choice` | `string` | ❌ | Force specific tool |
| `json_mode` | `bool` | ❌ | Request JSON-structured output |

**Message object:**
| Field | Type | Description |
|-------|------|-------------|
| `role` | `string` | `system`, `developer`, `user`, `assistant`, `tool` |
| `content` | `string\|[Mixed]` | Text or vision input |
| `name` | `string?` | Participant name |
| `tool_call_id` | `string?` | Tool call reference |
| `tool_calls` | `[ToolCall]?` | Tool invocations |

### Response

```json
{
  "id": "gemini-1785095504",
  "model": "gemini-flash-lite-latest",
  "provider": "gemini",
  "message": {
    "role": "assistant",
    "content": "Hello! I'm an AI assistant. How can I help you today?",
    "name": null,
    "tool_call_id": null,
    "tool_calls": null
  },
  "usage": {
    "prompt_tokens": 7,
    "completion_tokens": 16,
    "total_tokens": 23,
    "cost": 0.000005325
  },
  "latency_ms": 571.45
}
```

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `conversation_id` | `string?` | Attach to existing conversation for history |

---

## 1.2 Streaming Chat

Stream chat completion via Server-Sent Events (SSE).

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/ai/chat/stream` |

### Request Body

Same as Chat Completion but `stream` is forced to `true`.

### Response (SSE stream)

```
data: {"id":"gemini-x","model":"gemini-flash-lite-latest","provider":"gemini","content":"Hello","finish_reason":null,"usage":null}

data: {"id":"gemini-x","model":"gemini-flash-lite-latest","provider":"gemini","content":"!","finish_reason":null,"usage":null}

data: {"id":"gemini-x","model":"gemini-flash-lite-latest","provider":"gemini","content":"","finish_reason":"stop","usage":{"prompt_tokens":7,"completion_tokens":16,"total_tokens":23,"cost":5.325e-06}}
```

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `conversation_id` | `string?` | Attach to existing conversation for history |

---

## 1.3 Structured Output

Generate output matching a specific JSON Schema.

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/ai/chat/structured` |

### Request Body

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Generate a product with name, price, category"
    }
  ],
  "model": "gemini-flash-lite-latest",
  "schema_definition": {
    "type": "object",
    "properties": {
      "name": { "type": "string" },
      "price": { "type": "number" },
      "category": { "type": "string" }
    },
    "required": ["name", "price", "category"]
  }
}
```

### Response

```json
{
  "id": "gemini-1785095530",
  "model": "gemini-flash-lite-latest",
  "provider": "gemini",
  "message": {
    "role": "assistant",
    "content": "{\n  \"name\": \"Wireless Mouse\",\n  \"price\": 29.99,\n  \"category\": \"Electronics\"\n}",
    "name": null,
    "tool_call_id": null,
    "tool_calls": null
  },
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 32,
    "total_tokens": 42,
    "cost": 0.00001035
  },
  "latency_ms": 700.50
}
```

---

## 1.4 Tool/Function Calling

Chat with tool/function definitions. The model can decide to call tools instead of generating text.

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/ai/chat/tools` |

### Request Body

```json
{
  "messages": [
    {
      "role": "user",
      "content": "What is the weather in Paris?"
    }
  ],
  "model": "gemini-flash-lite-latest",
  "tools": [
    {
      "name": "get_weather",
      "description": "Get weather for a city",
      "parameters": {
        "type": "object",
        "properties": {
          "city": { "type": "string" }
        },
        "required": ["city"]
      }
    }
  ]
}
```

### Response

```json
{
  "id": "gemini-1785095531",
  "model": "gemini-flash-lite-latest",
  "provider": "gemini",
  "message": {
    "role": "assistant",
    "content": "",
    "name": null,
    "tool_call_id": null,
    "tool_calls": [
      {
        "id": "get_weather",
        "type": "function",
        "function_name": "get_weather",
        "arguments": "{\"city\": \"Paris\"}"
      }
    ]
  },
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 16,
    "total_tokens": 66,
    "cost": 0.00000855
  },
  "latency_ms": 491.18
}
```

---

## 1.5 Embeddings

Generate vector embeddings from text input.

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/ai/embeddings` |

### Request Body

```json
{
  "input": "Hello world",
  "model": "gemini-embedding-001"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `input` | `string \| [string]` | ✅ | Text(s) to embed |
| `model` | `string` | ✅ | Embedding model |

### Response

```json
{
  "model": "gemini-embedding-001",
  "provider": "gemini",
  "embeddings": [
    [ -0.02342, 0.01676, 0.00926, ... ]
  ],
  "usage": {
    "prompt_tokens": 2,
    "completion_tokens": 0,
    "total_tokens": 2,
    "cost": 0.00000005
  }
}
```

> **Note:** Embedding vector length depends on the model (e.g., gemini-embedding-001 returns 768 dimensions).

---

## 1.6 List Models

List all supported models across all providers.

| Method | Endpoint |
|--------|----------|
| **GET** | `/api/v1/ai/models` |

### Response (truncated)

```json
[
  {
    "name": "gpt-4o",
    "provider": "openai",
    "capabilities": {
      "vision": true,
      "json_mode": true,
      "tool_calling": true,
      "streaming": true,
      "embedding": false
    },
    "context_length": 128000,
    "pricing": {
      "prompt_cost_per_1m": 5.0,
      "completion_cost_per_1m": 15.0
    }
  },
  {
    "name": "gemini-flash-lite-latest",
    "provider": "gemini",
    "capabilities": {
      "vision": true,
      "json_mode": true,
      "tool_calling": true,
      "streaming": true,
      "embedding": false
    },
    "context_length": 1048576,
    "pricing": {
      "prompt_cost_per_1m": 0.075,
      "completion_cost_per_1m": 0.3
    }
  }
]
```

### Registered Models (25 total)

| Provider | Models |
|----------|--------|
| **OpenAI** | `gpt-4o`, `gpt-4o-mini`, `o1-mini`, `text-embedding-3-small`, `text-embedding-3-large` |
| **Azure** | `gpt-4o`, `gpt-4o-mini` |
| **Gemini** | `gemini-2.5-flash`, `gemini-flash-lite-latest`, `gemini-2.5-pro`, `gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-embedding-001` |
| **Claude** | `claude-3-5-sonnet-latest`, `claude-3-5-haiku-latest`, `claude-3-opus-latest` |
| **DeepSeek** | `deepseek-chat`, `deepseek-reasoner` |
| **Mistral** | `mistral-large-latest`, `open-mixtral-8x22b`, `mistral-embed` |
| **Ollama** | `llama3`, `mistral`, `nomic-embed-text` |

---

## 1.7 List Providers

List all supported providers with their aggregated capabilities.

| Method | Endpoint |
|--------|----------|
| **GET** | `/api/v1/ai/providers` |

### Response

```json
[
  {
    "provider": "openai",
    "supported_models": ["gpt-4o", "gpt-4o-mini", "o1-mini", "text-embedding-3-small", "text-embedding-3-large"],
    "capabilities": { "vision": true, "json_mode": true, "tool_calling": true, "streaming": true, "embedding": true }
  },
  {
    "provider": "gemini",
    "supported_models": ["gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-embedding-001"],
    "capabilities": { "vision": true, "json_mode": true, "tool_calling": true, "streaming": true, "embedding": true }
  }
]
```

---

## 1.8 Health Check (Default Provider)

| Method | Endpoint |
|--------|----------|
| **GET** | `/api/v1/ai/health` |

### Response

```json
{
  "status": "healthy",
  "provider": "gemini",
  "latency_ms": 284.63,
  "details": null
}
```

---

## 1.9 Provider Models

List models for a specific provider.

| Method | Endpoint |
|--------|----------|
| **GET** | `/api/v1/ai/provider/{provider}/models` |

### Path Params

| Param | Type | Description |
|-------|------|-------------|
| `provider` | `string` | Provider name (`openai`, `gemini`, `claude`, `deepseek`, `mistral`, `ollama`, `azure`) |

### Response

```json
[
  "gemini-2.5-flash",
  "gemini-flash-lite-latest",
  "gemini-2.5-pro",
  "gemini-2.0-flash",
  "gemini-1.5-flash",
  "gemini-1.5-pro",
  "gemini-embedding-001"
]
```

---

## 1.10 Provider Health Check

| Method | Endpoint |
|--------|----------|
| **GET** | `/api/v1/ai/provider/{provider}/health` |

### Response

```json
{
  "status": "healthy",
  "provider": "gemini",
  "latency_ms": 284.63,
  "details": null
}
```

---

# 2. Simple Chat

Minimal chat endpoint (auto-uses default model).

> **Importance:** Quick, no-fuss entry point for basic conversational AI — ideal for prototyping or simple assistants that don't need model selection.

| Method | Endpoint |
|--------|----------|
| **POST** | `/chat` |

### Request Body

```json
{
  "message": "Hello"
}
```

### Response

```json
{
  "response": "Hello! How can I help you today?"
}
```

---

# 3. AI-Powered Recommendations

Product recommendations and bundle suggestions powered by AI agents.

> **Importance:** Core **commerce intelligence**. These endpoints drive personalized product discovery and smart bundling with budget awareness — directly impacting conversion and average order value.

---

## 3.1 Product Recommendation

AI-powered product matching based on natural language query.

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/recommendations/chat` |

### Request Body

```json
{
  "message": "laptop for programming",
  "store_id": "store1",
  "customer_id": "cust123"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | `string` | ✅ | Natural language product query |
| `store_id` | `string` | ✅ | Store scope |
| `customer_id` | `string?` | ❌ | Personalize based on customer |

### Response (expected shape)

```json
{
  "query": "laptop for programming",
  "store_id": "store1",
  "customer_id": "cust123",
  "products": [
    {
      "product_id": "prod_001",
      "title": "MacBook Pro 14\"",
      "price": "1999.00",
      "currency": "USD",
      "image_url": "https://...",
      "product_url": "https://...",
      "specs": [{"key": "RAM", "value": "16GB"}],
      "match_reasons": ["Top-rated for programming"]
    }
  ],
  "rationale": "Recommended based on your query for programming laptops",
  "total_count": 1,
  "latency_ms": 1234.56
}
```

---

## 3.2 Bundle Suggestion

AI-generated product bundles with budget constraints and discount optimization.

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/recommendations/bundle-suggestion` |

### Request Body

```json
{
  "message": "I have $300 and want a monitor, keyboard, and mouse",
  "store_id": "store1",
  "customer_id": "cust123"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | `string` | ✅ | Natural language bundle request with budget |
| `store_id` | `string` | ✅ | Store scope |
| `customer_id` | `string?` | ❌ | Personalize based on customer |

### Response (expected shape)

```json
{
  "query": "I have $300 and want a monitor, keyboard, and mouse",
  "store_id": "store1",
  "customer_id": "cust123",
  "budget": 300.0,
  "bundles": [
    {
      "products": [
        {
          "product_id": "mon_001",
          "product_title": "24\" Monitor",
          "original_price": "199.99",
          "discount_pct": 10.0,
          "discount_amount": "20.00",
          "price_after_discount": "179.99"
        }
      ],
      "total_original": "199.99",
      "total_discount": "20.00",
      "total_after_discount": "179.99",
      "remaining_budget": 120.01,
      "within_budget": true,
      "promo_code": "BUNDLE10",
      "rank": 1
    }
  ],
  "promo_code": "BUNDLE10",
  "rationale": "Best value bundle within $300 budget",
  "latency_ms": 1500.0
}
```

---

# 4. RAG Chat

Retrieval-Augmented Generation chat — answers grounded in the store's knowledge base documents.

> **Importance:** The **knowledge layer** of the platform. RAG ensures answers are factual, cite sources, and reference the actual business documents (policies, product info, FAQs). Without this, the AI would hallucinate.

---

## 4.1 RAG Chat

| Method | Endpoint |
|--------|----------|
| **POST** | `/rag/chat` |

### Request Body

```json
{
  "message": "What are your business hours?",
  "store_id": "store1",
  "conversation_id": "conv_123",
  "organization_id": "org_1",
  "customer_id": "cust_1",
  "model": "gemini-flash-lite-latest",
  "temperature": 0.3,
  "max_tokens": 2048,
  "top_k": 5,
  "score_threshold": 0.0,
  "use_hybrid": false,
  "use_mmr": false,
  "rerank": false,
  "language": "en",
  "knowledge_scope": null,
  "stream": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | `string` | ✅ | User query (1-4000 chars) |
| `store_id` | `string` | ✅ | Store scope |
| `conversation_id` | `string?` | ❌ | Conversation tracking |
| `top_k` | `int` | ❌ | Number of chunks to retrieve (1-50, default: 5) |
| `score_threshold` | `float` | ❌ | Minimum similarity score (0.0-1.0) |
| `use_hybrid` | `bool` | ❌ | Enable hybrid keyword+vector search |
| `use_mmr` | `bool` | ❌ | Enable MMR diversity |
| `rerank` | `bool` | ❌ | Enable LLM cross-encoder re-ranking |

### Response (expected shape)

```json
{
  "response": "Our business hours are Monday to Friday, 9 AM to 6 PM EST.",
  "citations": [
    {
      "index": 0,
      "chunk_id": "chunk_001",
      "document_title": "Store Policy",
      "content_snippet": "Business hours: Mon-Fri 9AM-6PM EST",
      "score": 0.95,
      "rank": 1
    }
  ],
  "chunk_references": [
    {
      "chunk_id": "chunk_001",
      "document_id": "doc_001",
      "document_title": "Store Policy",
      "content_snippet": "Business hours: Mon-Fri 9AM-6PM EST",
      "score": 0.95,
      "rank": 1
    }
  ],
  "confidence_score": 0.95,
  "latency_ms": 1200.0,
  "model": "gemini-flash-lite-latest",
  "provider": "gemini",
  "usage": { "prompt_tokens": 150, "completion_tokens": 30, "total_tokens": 180, "cost": 0.00002 },
  "business_summary_version": 2,
  "conversation_id": "conv_123"
}
```

---

## 4.2 RAG Streaming Chat

| Method | Endpoint |
|--------|----------|
| **POST** | `/rag/chat/stream` |

Same request body as RAG chat. Returns SSE stream with chunk-by-chunk content and citations.

---

# 5. Knowledge Base

Full CRUD + AI-powered operations on the knowledge base (documents, chunks, summaries, uploads).

Prefix is configurable; default: `/api/v1/knowledge-base`.

> **Importance:** The **document management layer** — stores, processes, chunks, embeds, and indexes business documents so the RAG system can answer questions accurately.

---

## 5.1 Documents CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/api/v1/knowledge-base/documents` | Create document |
| **GET** | `/api/v1/knowledge-base/documents` | List documents (paginated) |
| **GET** | `/api/v1/knowledge-base/documents/{id}` | Get document by ID |
| **PUT** | `/api/v1/knowledge-base/documents/{id}` | Update document |
| **DELETE** | `/api/v1/knowledge-base/documents/{id}` | Delete document |

### Query Params (List)

| Param | Type | Description |
|-------|------|-------------|
| `page` | `int` | Page number (default: 1) |
| `page_size` | `int` | Items per page (default: 20, max: 100) |
| `store_id` | `string?` | Filter by store |
| `status` | `string?` | Filter by status |

### Document Schema

```json
{
  "id": "doc_001",
  "store_id": "store1",
  "title": "Shipping Policy",
  "status": "published",
  "language": "en",
  "chunking_strategy": "recursive_character",
  "metadata": {
    "source_type": "manual",
    "language": "en",
    "category": null,
    "tags": [],
    "attributes": {}
  },
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

---

## 5.2 Chunks CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/api/v1/knowledge-base/chunks` | Create chunk |
| **GET** | `/api/v1/knowledge-base/chunks` | List chunks (paginated) |
| **GET** | `/api/v1/knowledge-base/chunks/{id}` | Get chunk by ID |
| **PUT** | `/api/v1/knowledge-base/chunks/{id}` | Update chunk |
| **DELETE** | `/api/v1/knowledge-base/chunks/{id}` | Delete chunk |

---

## 5.3 Summaries CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/api/v1/knowledge-base/summaries` | Create summary |
| **GET** | `/api/v1/knowledge-base/summaries` | List summaries |
| **GET** | `/api/v1/knowledge-base/summaries/{id}` | Get summary |
| **PUT** | `/api/v1/knowledge-base/summaries/{id}` | Update summary |
| **DELETE** | `/api/v1/knowledge-base/summaries/{id}` | Delete summary |

---

## 5.4 Upload Document

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/uploads` |

### Form Data

| Field | Type | Description |
|-------|------|-------------|
| `file` | `file` | Document file (PDF, DOCX, TXT, etc.) |
| `uploaded_by` | `string` | Uploader identifier |
| `organization_id` | `string` | Organization scope |
| `store_id` | `string` | Store scope |
| `knowledge_scope` | `string?` | Scope (default: `general`) |

---

## 5.5 Business Summary — AI Generation

AI-generated business summary from uploaded documents.

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/summaries/generate` |

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `store_id` | `string` | ✅ Store to generate summary for |

### Optional Body

```json
{
  "model": "gpt-4o-mini",
  "temperature": 0.3,
  "max_tokens": 4096
}
```

### Response

```json
{
  "id": "summ_001",
  "document_id": "doc_001",
  "version_number": 1,
  "title": "Store Business Summary",
  "summary": "This store sells electronics...",
  "metadata": {},
  "sections": {},
  "document_count": 5,
  "model": "gemini-flash-lite-latest",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

---

## 5.6 Business Summary — Regenerate

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/summaries/regenerate` |

Same params as generate.

---

## 5.7 Business Summary — History

| Method | Endpoint |
|--------|----------|
| **GET** | `/api/v1/knowledge-base/summaries/history` |

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `store_id` | `string` | ✅ Store filter |
| `page` | `int` | Page number |
| `page_size` | `int` | Items per page |

---

## 5.8 Unified — Upload

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/upload` |

Same as Upload Document above.

---

## 5.9 Unified — Process Document

Process a document asynchronously (extract + normalize text).

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/process` |

### Request Body

```json
{
  "document_id": "doc_001",
  "file_path": "/path/to/file.pdf",
  "mime_type": "application/pdf",
  "also_chunk": true,
  "strategy": "recursive_character",
  "chunk_size": 1000,
  "overlap": 200,
  "store_id": "store1",
  "organization_id": "org_1",
  "triggered_by": "user_1"
}
```

### Response (202 Accepted)

```json
{
  "job_id": "job_001",
  "job_type": "document_processing_with_chunking",
  "status": "pending",
  "message": "Processing job job_001 + chunk job job_002 enqueued"
}
```

---

## 5.10 Unified — Generate Chunks

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/chunk` |

### Request Body

```json
{
  "document_id": "doc_001",
  "strategy": "recursive_character",
  "chunk_size": 1000,
  "overlap": 200,
  "store_id": "store1",
  "organization_id": "org_1",
  "triggered_by": "user_1"
}
```

---

## 5.11 Unified — Generate Embeddings

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/embed` |

### Request Body

```json
{
  "document_id": "doc_001",
  "model": "gemini-embedding-001",
  "sync_to_vector_store": true,
  "collection_name": "kb_default",
  "store_id": "store1",
  "organization_id": "org_1",
  "triggered_by": "user_1"
}
```

---

## 5.12 Unified — Semantic Search

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/search` |

### Request Body

```json
{
  "query": "What is your return policy?",
  "top_k": 10,
  "score_threshold": 0.0,
  "use_hybrid": false,
  "use_mmr": false,
  "mmr_lambda": 0.7,
  "rerank": false,
  "rerank_top_k": 5,
  "embedding_model": "gemini-embedding-001",
  "store_id": "store1",
  "organization_id": "org_1",
  "language": "en",
  "knowledge_scope": "general",
  "business_version": 1
}
```

---

## 5.13 Unified — Hybrid Search

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/search/hybrid` |

Same body as semantic search. Forces `use_hybrid: true`.

---

## 5.14 Unified — Generate/Regenerate Summary

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/knowledge-base/summary` | Generate |
| **POST** | `/api/v1/knowledge-base/summary/regenerate` | Regenerate |

---

## 5.15 Unified — Get Job Status

| Method | Endpoint |
|--------|----------|
| **GET** | `/api/v1/knowledge-base/jobs/{job_id}` |

---

# 6. Knowledge Jobs

Async job management for document processing, chunking, embedding, and vector sync operations.

> **Importance:** Enables **async processing** of large documents. Without jobs, uploading a 100-page PDF would block the API. Jobs allow the system to queue, track progress, retry failures, and scale horizontally via Celery workers.

---

## 6.1 Document Processing Job

| Method | Endpoint |
|--------|----------|
| **POST** | `/knowledge/jobs/document-processing` |

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `document_id` | `string` | ✅ Document to process |
| `file_path` | `string` | ✅ File location |
| `mime_type` | `string?` | ❌ |
| `store_id` | `string?` | ❌ |
| `organization_id` | `string?` | ❌ |
| `triggered_by` | `string?` | ❌ |

---

## 6.2 Chunk Generation Job

| Method | Endpoint |
|--------|----------|
| **POST** | `/knowledge/jobs/chunk-generation` |

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `document_id` | `string` | ✅ |
| `strategy` | `string?` | Chunking strategy (default: `recursive_character`) |
| `chunk_size` | `int?` | 100-5000 (default: 1000) |
| `overlap` | `int?` | 0-1000 (default: 200) |

---

## 6.3 Summary Generation Job

| Method | Endpoint |
|--------|----------|
| **POST** | `/knowledge/jobs/summary-generation` |

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `store_id` | `string` | ✅ |
| `model` | `string?` | LLM model override |
| `organization_id` | `string?` | ❌ |
| `triggered_by` | `string?` | ❌ |

---

## 6.4 Embedding Generation Job

| Method | Endpoint |
|--------|----------|
| **POST** | `/knowledge/jobs/embedding-generation` |

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `chunk_ids` | `[string]` | ✅ Chunks to embed |
| `model` | `string?` | Embedding model (default: `gemini-embedding-001`) |

---

## 6.5 Vector Sync Job

| Method | Endpoint |
|--------|----------|
| **POST** | `/knowledge/jobs/vector-sync` |

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `chunk_ids` | `[string]` | ✅ Chunks to sync |
| `collection_name` | `string?` | Qdrant collection (default: `kb_default`) |
| `model` | `string?` | Embedding model |

---

## 6.6 Get Job Status

| Method | Endpoint |
|--------|----------|
| **GET** | `/knowledge/jobs/{job_id}` |

### Response

```json
{
  "id": "job_001",
  "job_type": "document_processing",
  "status": "completed",
  "progress": 1.0,
  "payload": { "document_id": "doc_001", "file_path": "/tmp/doc.pdf" },
  "result": { "pages": 5, "char_count": 15000 },
  "error_message": null,
  "retry_count": 0,
  "max_retries": 3,
  "store_id": "store1",
  "organization_id": "org_1",
  "triggered_by": "user_1",
  "celery_task_id": "celery_task_001",
  "started_at": "2025-01-01T00:00:00Z",
  "completed_at": "2025-01-01T00:01:00Z",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:01:00Z"
}
```

---

## 6.7 List Jobs

| Method | Endpoint |
|--------|----------|
| **GET** | `/knowledge/jobs` |

### Query Params

| Param | Type | Description |
|-------|------|-------------|
| `page` | `int` | Page number |
| `page_size` | `int` | Items per page (1-100) |
| `status` | `string?` | Filter by status |
| `job_type` | `string?` | Filter by type |
| `store_id` | `string?` | Filter by store |

---

## 6.8 Requeue Job

Requeue a failed/dead-letter job for retry.

| Method | Endpoint |
|--------|----------|
| **POST** | `/knowledge/jobs/{job_id}/requeue` |

---

# 7. Knowledge Retrieval

Direct semantic search over the knowledge base vectors.

> **Importance:** The **search engine** for the knowledge base. Used by RAG and also directly by external services that need to programmatically search business documents.

---

## 7.1 Semantic Search

| Method | Endpoint |
|--------|----------|
| **POST** | `/knowledge/retrieval/search` |

### Request Body

```json
{
  "query": "What is your return policy?",
  "top_k": 10,
  "score_threshold": 0.0,
  "use_hybrid": false,
  "use_mmr": false,
  "mmr_lambda": 0.7,
  "rerank": false,
  "rerank_top_k": 5,
  "embedding_model": "gemini-embedding-001",
  "organization_id": "org_1",
  "store_id": "store1",
  "language": "en",
  "document_type": "policy",
  "knowledge_scope": "general",
  "business_version": 1
}
```

### Response

```json
{
  "query": "What is your return policy?",
  "results": [
    {
      "chunk_id": "chunk_001",
      "document_id": "doc_001",
      "document_title": "Return Policy",
      "chunk_index": 0,
      "content": "Items can be returned within 30 days...",
      "score": 0.95,
      "rank": 1,
      "metadata": {},
      "language": "en",
      "source_type": "manual"
    }
  ],
  "total_count": 1,
  "strategy": "vector_search",
  "latency_ms": 45.67,
  "filters_applied": { "store_id": "store1", "language": "en" }
}
```

---

# 8. Integration (AI-Agent)

AI-agent-driven third-party API integration — parse API specs, map entities, and sync data.

> **Importance:** **Vendor onboarding automation**. This AI agent can take any 3rd-party API specification (OpenAPI, etc.) and automatically build the integration mappings, entity relationships, and sync workflows — dramatically reducing manual integration work.

---

## 8.1 Parse API Spec (Rule-Based)

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/integration/schemas/parse` |

### Request Body

```json
{
  "platform_name": "Shopify",
  "raw_spec": "{openapi: 3.0, info: {title: Shopify API, version: 2024-01}, ...}"
}
```

---

## 8.2 Parse API Spec (AI Agent)

AI agent analyzes the spec intelligently, identifying entities, features, and unsupported endpoints.

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/integration/schemas/agent-parse` |

### Request Body

```json
{
  "platform_name": "Shopify",
  "raw_spec": "{...}"
}
```

### Response

```json
{
  "platform_name": "Shopify",
  "base_url": "https://shopify.com/api/2024-01",
  "api_version": "2024-01",
  "entities": [
    {
      "entity_type": "product",
      "list_path": "/products",
      "list_method": "GET",
      "detail_path": "/products/{id}",
      "detail_method": "GET",
      "id_field": "id",
      "pagination": { "type": "cursor", "cursor_field": "page_info" },
      "field_mappings": [
        { "source_field": "title", "target_field": "name", "transform": null }
      ]
    }
  ],
  "feature_analysis": {
    "supported_features": ["products", "orders", "customers"],
    "partially_supported": ["inventory"],
    "unsupported_features": [],
    "notes": "All core ecommerce features supported"
  },
  "capabilities": {},
  "warnings": [],
  "errors": []
}
```

---

## 8.3 Agent Full Sync Workflow

End-to-end AI agent workflow: parse spec → create connection → map entities → sync data.

| Method | Endpoint |
|--------|----------|
| **POST** | `/api/v1/integration/agent-sync` |

---

## 8.4 Connections CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/api/v1/integration/connections` | Create connection |
| **GET** | `/api/v1/integration/connections` | List connections |
| **GET** | `/api/v1/integration/connections/{id}` | Get connection |
| **PUT** | `/api/v1/integration/connections/{id}/mappings` | Update mappings |
| **PUT** | `/api/v1/integration/connections/{id}/credentials` | Update credentials |
| **POST** | `/api/v1/integration/connections/{id}/sync` | Trigger sync |
| **DELETE** | `/api/v1/integration/connections/{id}` | Delete connection |

---

# 9. Health

| Method | Endpoint |
|--------|----------|
| **GET** | `/health/` |

### Response

```json
{
  "status": "AI Service is live !"
}
```

---

# Quick Reference: All Endpoints Summary

| # | Method | Endpoint | Group |
|---|--------|----------|-------|
| 1 | **POST** | `/api/v1/ai/chat` | AI Core |
| 2 | **POST** | `/api/v1/ai/chat/stream` | AI Core |
| 3 | **POST** | `/api/v1/ai/chat/structured` | AI Core |
| 4 | **POST** | `/api/v1/ai/chat/tools` | AI Core |
| 5 | **POST** | `/api/v1/ai/embeddings` | AI Core |
| 6 | **GET** | `/api/v1/ai/models` | AI Core |
| 7 | **GET** | `/api/v1/ai/providers` | AI Core |
| 8 | **GET** | `/api/v1/ai/health` | AI Core |
| 9 | **GET** | `/api/v1/ai/provider/{provider}/models` | AI Core |
| 10 | **GET** | `/api/v1/ai/provider/{provider}/health` | AI Core |
| 11 | **POST** | `/chat` | Simple Chat |
| 12 | **POST** | `/api/v1/recommendations/chat` | Recommendations |
| 13 | **POST** | `/api/v1/recommendations/bundle-suggestion` | Recommendations |
| 14 | **POST** | `/rag/chat` | RAG |
| 15 | **POST** | `/rag/chat/stream` | RAG |
| 16-20 | CRUD | `/api/v1/knowledge-base/documents[/{id}]` | Knowledge |
| 21-25 | CRUD | `/api/v1/knowledge-base/chunks[/{id}]` | Knowledge |
| 26-30 | CRUD | `/api/v1/knowledge-base/summaries[/{id}]` | Knowledge |
| 31-34 | CRUD | `/api/v1/knowledge-base/uploads[/{id}]` | Knowledge |
| 35 | **POST** | `/api/v1/knowledge-base/summaries/generate` | Knowledge |
| 36 | **POST** | `/api/v1/knowledge-base/summaries/regenerate` | Knowledge |
| 37 | **GET** | `/api/v1/knowledge-base/summaries/history` | Knowledge |
| 38 | **POST** | `/api/v1/knowledge-base/upload` | Knowledge (Unified) |
| 39 | **POST** | `/api/v1/knowledge-base/process` | Knowledge (Unified) |
| 40 | **POST** | `/api/v1/knowledge-base/chunk` | Knowledge (Unified) |
| 41 | **POST** | `/api/v1/knowledge-base/embed` | Knowledge (Unified) |
| 42 | **POST** | `/api/v1/knowledge-base/search` | Knowledge (Unified) |
| 43 | **POST** | `/api/v1/knowledge-base/search/hybrid` | Knowledge (Unified) |
| 44 | **POST** | `/api/v1/knowledge-base/summary` | Knowledge (Unified) |
| 45 | **POST** | `/api/v1/knowledge-base/summary/regenerate` | Knowledge (Unified) |
| 46 | **GET** | `/api/v1/knowledge-base/jobs/{job_id}` | Knowledge (Unified) |
| 47-54 | CRUD | `/knowledge/jobs/*` | Knowledge Jobs |
| 55 | **POST** | `/knowledge/retrieval/search` | Knowledge Retrieval |
| 56 | **POST** | `/api/v1/integration/schemas/parse` | Integration |
| 57 | **POST** | `/api/v1/integration/schemas/agent-parse` | Integration |
| 58 | **POST** | `/api/v1/integration/agent-sync` | Integration |
| 59-65 | CRUD | `/api/v1/integration/connections[/{id}]/*` | Integration |
