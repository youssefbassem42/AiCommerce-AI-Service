# Knowledge Sync & Versioning

## KnowledgeSyncCoordinator

**File:** `app/application/knowledge/coordinator.py`

Orchestrates knowledge synchronization for a single store tenant. Detects document changes via checksum comparison, invalidates stale data, enqueues background jobs, and manages knowledge version tracking.

### Sync Flow

```
run_sync()
  │
  ├─ _load_current_version()        → current version number (0 if none)
  │
  ├─ find_by_store_id()             → all documents for this store
  │
  ├─ For each document:
  │    ├─ _document_changed()       → compare checksum vs stored
  │    ├─ changed → add to changed list
  │    └─ unchanged → increment skipped counter
  │
  ├─ If no changes → return (no_changes status)
  │
  ├─ _start_version(current + 1)    → mark previous as "previous", insert new "active"
  │
  ├─ For each changed document:
  │    ├─ _invalidate_document_data()  → mark existing as "invalidated"
  │    └─ Enqueue or run inline:
  │         ├─ kb.extract_document     → extract text from source
  │         ├─ kb.chunk_document       → split into chunks
  │         ├─ kb.embed_chunks         → generate embeddings
  │         └─ kb.sync_vector_db       → upsert to Qdrant
  │
  ├─ _regenerate_summary()          → generate new business summary via LLM
  │
  └─ _complete_version()            → update version record with final counts
```

### SyncReport

Returned by `run_sync()`, provides full visibility into the sync cycle:

| Field | Type | Description |
|---|---|---|
| `current_version` | int | Version before sync |
| `new_version` | int | Version after sync (0 if no changes) |
| `total_files` | int | Total documents evaluated |
| `files_skipped` | int | Documents unchanged |
| `files_processed` | int | Documents needing re-processing |
| `chunks_generated` | int | Chunks created this cycle |
| `embeddings_generated` | int | Embeddings generated |
| `summary_updated` | bool | Business summary regenerated |
| `vectors_synced` | bool | Vector DB updated |
| `sync_status` | str | `pending`, `completed`, `no_changes` |
| `errors` | list[str] | Any errors encountered |

## Change Detection

Documents are identified as changed when:
1. No versions exist (new document) → always process
2. Latest version has no checksum → process
3. Stored `source_checksum` differs from latest version checksum → process

Checksum is SHA-256 of the file content, computed in 64KB blocks.

## Knowledge Versioning

**Value Object:** `app/domain/knowledge/value_objects/knowledge_version.py`
**Document:** `app/infrastructure/mongodb/documents/knowledge_version_document.py`
**Collection:** `knowledge_versions`

### Version States

| Status | Description |
|---|---|
| `active` | Current active version — used for retrieval |
| `previous` | Superseded by a newer version — preserved for rollback |
| `rolled_back` | Manually rolled back |

### Version Record

| Field | Type | Description |
|---|---|---|
| `organization_id` | str | Tenant scope |
| `store_id` | str | Store scope |
| `version_number` | int | Monotonically increasing |
| `previous_version` | int | Previous version for rollback |
| `status` | str | active / previous / rolled_back |
| `document_count` | int | Documents in this version |
| `chunk_count` | int | Chunks in this version |
| `summary_generated` | bool | Business summary completed |
| `embeddings_generated` | bool | Embeddings generated |
| `vectors_synced` | bool | Vector DB synced |
| `started_at` | datetime | When sync began |
| `completed_at` | datetime | When sync completed |

## Celery Tasks

| Task Name | Queue | When Enqueued |
|---|---|---|
| `kb.extract_document` | ingestion | Document changed |
| `kb.chunk_document` | ingestion | Extraction complete |
| `kb.embed_chunks` | embedding | Chunking complete |
| `kb.sync_vector_db` | embedding | Embeddings ready |
| `kb.generate_summary` | summarization | All docs processed |
| `kb.bump_version` | default | Summary complete |

When `enqueue_background=False`, all steps run inline (useful for testing/playground).
