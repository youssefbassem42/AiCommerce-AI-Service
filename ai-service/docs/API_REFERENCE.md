# API Reference

## TenantContextResolver

**Module:** `app.application.rag.resolver`

### `TenantContextResolver(store_registry=None)`

| Method | Parameters | Returns | Description |
|---|---|---|---|
| `register_store(slug, config)` | slug: str, config: dict | None | Register a store for resolution |
| `from_config(config)` | config: dict | TenantContext | Build TenantContext from raw dict |
| `from_slug(slug)` | slug: str | TenantContext | Resolve from store slug |
| `from_jwt(token)` | token: str | TenantContext | Resolve from JWT claims |
| `from_api_key(api_key)` | api_key: str | TenantContext | Resolve from API key hash |
| `from_webhook_payload(payload)` | payload: dict | TenantContext | Resolve from webhook body |
| `from_embed_widget(config)` | config: dict | TenantContext | Resolve from widget config |
| `from_admin_session(user_id)` | user_id: str | TenantContext | Resolve from admin session |

## ContextBuilder

**Module:** `app.application.rag.context_builder`

### `ContextBuilder(tenant, retriever, knowledge_repository, business_summary_repository)`

| Method | Parameters | Returns | Description |
|---|---|---|---|
| `build(query)` | query: str | BuiltContext | Load all context for a query |

### `BuiltContext`

| Field | Type | Description |
|---|---|---|
| `business_summary` | str\|None | Latest business summary text |
| `business_summary_version` | int\|None | Version of the summary |
| `business_summary_sections` | dict | Individual summary sections |
| `chunks` | list[RetrievedChunkDTO] | Deduplicated retrieved chunks |
| `knowledge_version` | KnowledgeVersionInfo\|None | Active knowledge version |
| `active_version_number` | int | Version number shorthand |
| `merchant_profile` | str\|None | Merchant information |
| `store_info` | str\|None | Store configuration info |
| `tenant` | TenantContext\|None | Resolved tenant |
| `latency_ms` | float | Build time in milliseconds |
| `total_chunks_retrieved` | int | Raw chunks before dedup |

## PromptBuilder

**Module:** `app.application.rag.prompt_builder`

### `PromptBuilder(developer_prompt, max_chunk_chars, max_chunks)`

| Method | Parameters | Returns | Description |
|---|---|---|---|
| `build(user_message, context, conversation_history)` | message, BuiltContext, history\|None | list[MessageDTO] | Full message list for ChatService |
| `build_single_prompt(user_message, context, conversation_history)` | same as above | str | Single concatenated prompt string |

### Assembled Prompt Structure

```
System: RAG_SYSTEM_PROMPT + Business Summary (v{N}) + Chunks + Placeholder
[Conversation History (last N pairs)]
User: {original message}
```

## RetrieverService (Extended)

**Module:** `app.application.knowledge.retrieval.service`

### Constructor Parameter

```python
RetrieverService(
    vector_store: VectorStore,
    llm_provider: BaseLLMProvider,
    reranker: ReRanker | None = None,
    default_config: RetrievalConfig | None = None,
    tenant: TenantContext | None = None,      # NEW
)
```

### Auto-Enforced Filters

When a `tenant` is provided, every search automatically includes:

| Filter | Value | Reason |
|---|---|---|
| `organization_id` | `tenant.organization_id` | No global retrieval |
| `store_id` | `tenant.store_id` | No cross-store leakage |
| `knowledge_version` | `tenant.knowledge_version` | Only current version |
| `document_status` | `active` | Only active documents |

## RetrievalFilters (Extended)

**Module:** `app.application.knowledge.retrieval.config`

### New Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `document_status` | str\|None | None | Filter by document status (auto-defaults to "active") |
| `knowledge_version` | int\|None | None | Filter by knowledge base version |

## KnowledgeSyncCoordinator

**Module:** `app.application.knowledge.coordinator`

### `KnowledgeSyncCoordinator(tenant, document_service, chunk_service, summary_service, knowledge_repository, ...)`

| Method | Parameters | Returns | Description |
|---|---|---|---|
| `run_sync(file_paths, chunk_size, chunk_overlap, chunk_strategy, summary_model, enqueue_background)` | optional overrides | SyncReport | Full sync cycle for the tenant's store |

### `SyncReport`

| Field | Type | Description |
|---|---|---|
| `tenant` | TenantContext | The synced tenant |
| `current_version` | int | Version before sync |
| `new_version` | int | Version after sync |
| `total_files` | int | Total documents evaluated |
| `files_skipped` | int | Unchanged documents |
| `files_processed` | int | Reprocessed documents |
| `chunks_generated` | int | New chunks created |
| `embeddings_generated` | int | New embeddings |
| `summary_updated` | bool | Business summary regenerated |
| `vectors_synced` | bool | Vector DB updated |
| `sync_status` | str | pending / completed / no_changes |
| `errors` | list[str] | Sync errors |
| `to_dict()` | → dict | Serializable representation |
