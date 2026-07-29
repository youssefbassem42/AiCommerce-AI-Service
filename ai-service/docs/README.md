# AI Commerce — Tenant-Aware RAG

## Overview

Intelligent, tenant-aware Retrieval-Augmented Generation (RAG) system for the AI Commerce Platform. Every store operates on a fully isolated knowledge base with automatic tenant resolution, scoped retrieval, and transparent context assembly.

## Feature Summary

| Feature | Status | Description |
|---|---|---|
| TenantContextResolver | ✅ Done | Resolves current store from JWT, API Key, Webhook, Widget, Admin, Slug |
| ContextBuilder | ✅ Done | Loads business summary + knowledge chunks + merchant/store info, deduplicates, ranks |
| RetrieverService Auto-Scope | ✅ Done | Always filters by tenant org, store, active version, active status |
| PromptBuilder | ✅ Done | Assembles final prompt using existing templates, delegates to ChatService |
| KnowledgeSyncCoordinator | ✅ Done | Change detection, version bumping, background job enqueue |
| Knowledge Versioning | ✅ Done | MongoDB-backed version tracking per store |
| Playground | ✅ Done | Multi-tenant CLI with full pipeline, sync, context, and chat display |

## Documentation Index

| Document | Description |
|---|---|
| [Architecture](ARCHITECTURE.md) | System components, data flow, module boundaries |
| [Tenant Isolation](TENANT_ISOLATION.md) | Tenant model, resolver strategies, scope enforcement |
| [Knowledge Sync](KNOWLEDGE_SYNC.md) | Change detection, versioning, coordinator orchestration |
| [API Reference](API_REFERENCE.md) | Public interfaces, DTOs, service contracts |
| [Playground Guide](PLAYGROUND.md) | Running the multi-tenant RAG playground |

## Quick Start

```bash
# Install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Run for a specific store
python scripts/rag_playground.py --store electronics
python scripts/rag_playground.py --store fashion
python scripts/rag_playground.py --store pharmacy
```

## Tenant Registry

| Store Slug | Organization | Store ID | Document |
|---|---|---|---|
| `electronics` | `org_elec_001` | `store_elec_001` | salla_file.pdf |
| `fashion` | `org_fashion_002` | `store_fashion_002` | amazon-business-faq.pdf |
| `pharmacy` | `org_pharma_003` | `store_pharma_003` | (custom) |
