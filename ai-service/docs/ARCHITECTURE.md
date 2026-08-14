# Architecture — Tenant-Aware RAG

## System Context

The Tenant-Aware RAG system extends the existing AI Commerce platform with intelligent tenant isolation. Every request is automatically scoped to the correct store without the customer ever needing to specify it.

```
┌──────────────┐     ┌──────────────────────┐     ┌──────────────┐
│   Client     │────▶│  TenantContextResolver│────▶│  TenantContext│
│ (JWT/ApiKey) │     │  (JWT/WEBHOOK/SLUG)  │     │  (Frozen VO)  │
└──────────────┘     └──────────────────────┘     └──────────────┘
                                                          │
                                                          ▼
┌──────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  ChatService │◀────│    PromptBuilder      │◀────│  ContextBuilder│
│  (LLM call)  │     │  (assemble prompt)    │     │  (merge data)  │
└──────────────┘     └──────────────────────┘     └──────────────┘
                                                          │
                                            ┌─────────────┼─────────────┐
                                            ▼             ▼             ▼
                                     ┌──────────┐ ┌──────────┐ ┌──────────────┐
                                     │ Business  │ │Retriever │ │ Knowledge    │
                                     │ Summary   │ │ Service  │ │ Version      │
                                     │ (MongoDB) │ │(Qdrant)  │ │ (MongoDB)    │
                                     └──────────┘ └──────────┘ └──────────────┘
```

## Module Boundaries

### `app/application/rag/` — RAG Orchestration Layer

| File | Responsibility |
|---|---|
| `resolver.py` | TenantContextResolver — determines the current store from auth context |
| `context_builder.py` | ContextBuilder — loads and merges all tenant-scoped data |
| `prompt_builder.py` | PromptBuilder — assembles the final LLM prompt |
| `prompt.py` | Existing prompt templates (not modified) |
| `service.py` | Existing RagOrchestrationService (not modified) |
| `dedup.py` | Existing chunk deduplication (not modified) |
| `dto.py` | Existing DTOs (not modified) |

### `app/application/knowledge/` — Knowledge Domain

| File | Responsibility |
|---|---|
| `coordinator.py` | KnowledgeSyncCoordinator — orchestrates per-store knowledge sync |
| `services.py` | Existing CRUD services (not modified) |
| `retrieval/service.py` | RetrieverService — tenant-scoped vector + keyword search |
| `retrieval/config.py` | RetrievalFilters, RetrievalConfig — extended with document_status, knowledge_version |

### `app/domain/knowledge/value_objects/` — Domain Value Objects

| File | Responsibility |
|---|---|
| `tenant_context.py` | TenantContext — frozen VO with org/store/merchant/integration/version |
| `knowledge_version.py` | KnowledgeVersionInfo — version tracking with counts and status flags |

## Data Flow — Request to Response

```
1. Request arrives (with JWT / API Key / Store Slug)
       │
2. TenantContextResolver resolves → TenantContext
       │
3. KnowledgeSyncCoordinator checks for document changes
       │  ├─ Loads current knowledge version
       │  ├─ Compares checksums per document
       │  └─ Bumps version if changes detected
       │
4. ContextBuilder.build(query):
       │  ├─ _load_business_summary()     → latest BusinessSummary
       │  ├─ _retrieve_chunks(query)      → RetrieverService (tenant-scoped)
       │  └─ _load_knowledge_version()    → active KnowledgeVersionInfo
       │
5. PromptBuilder.build(user_msg, context, history)
       │  ├─ System: RAG_SYSTEM_PROMPT + Business Summary + Chunks
       │  ├─ Conversation history (if any)
       │  └─ User: original message
       │
6. ChatService.chat(messages) → Response
       │
7. Response includes: answer, citations, chunks, version, tenant
```

## Tenant Scoping Chain

```
TenantContextResolver
    ↓
TenantContext { organization_id, store_id, knowledge_version }
    ↓
RetrievalFilters { org_id, store_id, doc_status=active, knowledge_version }
    ↓
Qdrant payload filter + MongoDB query filter
    ↓
100% tenant-scoped results — never global
```
