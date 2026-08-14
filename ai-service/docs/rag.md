# RAG Pipeline

Retrieval-Augmented Generation for knowledge-base queries.

## Pipeline Stages

```
Document → Loader → Parser → Chunker → Embedder → Vector Store
                                                        ↓
User Query → Retriever → Reranker → Context Builder → LLM → Answer
```

## Components

| Component | Status | Description |
|-----------|--------|-------------|
| Loaders | 📝 Phase 04 | PDF, HTML, Markdown, JSON, CSV, DOCX |
| Parsers | 📝 Phase 04 | Structure extraction (tables, headings, code) |
| Chunkers | 📝 Phase 04 | Token, semantic, recursive, code-aware |
| Embedders | 📝 Phase 04 | OpenAI, Azure, Ollama with LRU cache |
| Vector Store | 📝 Phase 04 | Qdrant wrapper with payload filtering |
| Retrievers | 📝 Phase 04 | Vector, hybrid (dense+sparse), multi-vector, contextual |
| Rerankers | 📝 Phase 04 | LLM, cross-encoder, MMR |
| Pipeline | 📝 Phase 04 | Orchestrator tying all stages together |

## Current RAG (Pre-Phase 04)

The current implementation uses `RagOrchestrationService` with:
- Basic Qdrant retrieval
- Context building with tenant isolation
- Prompt assembly with business summaries
- ChatService for final LLM call

Phase 04 will replace the ad-hoc retrieval with a full pipeline including advanced chunking, hybrid search, and reranking.

## Tenant Isolation

Every RAG query is tenant-scoped via `TenantContext`:
- `store_id` filters Qdrant payloads
- `knowledge_version` ensures version consistency
- Business summaries are store-specific
