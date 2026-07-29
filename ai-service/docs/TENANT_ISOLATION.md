# Tenant Isolation

## Principle

Every store is a first-class tenant. No operation — retrieval, sync, versioning, or context assembly — can leak data between stores. The end user never chooses a store; the system resolves it automatically.

## TenantContext (Value Object)

**File:** `app/domain/knowledge/value_objects/tenant_context.py`

An immutable frozen dataclass carrying all tenant identifiers:

| Field | Type | Description |
|---|---|---|
| `organization_id` | `str` | Owning organization (required) |
| `store_id` | `str` | Active store (required) |
| `merchant_id` | `str` | Merchant running the store |
| `integration_id` | `str` | Active store integration ID |
| `store_slug` | `str` | Human-readable slug (electronics, fashion) |
| `language` | `str` | Default language (en, fr) |
| `currency` | `str` | Default currency (USD, EUR) |
| `timezone` | `str` | Store timezone |
| `knowledge_version` | `int` | Current knowledge base version |
| `vector_namespace` | `str` | Qdrant collection suffix |

**Key Methods:**
- `scope_filter()` → `{organization_id, store_id}` — reusable filter dict
- `collection_name` (property) → `kb_{vector_namespace}` — Qdrant collection name

## TenantContextResolver

**File:** `app/application/rag/resolver.py`

Resolves the current store from any authentication context.

| Method | Source | Example |
|---|---|---|
| `from_jwt(token)` | JWT claims | `org_id`, `store_id`, `slug` in token payload |
| `from_api_key(key)` | API key → SHA-256 hash | Matches against registered store configs |
| `from_webhook_payload(payload)` | Webhook event body | Organization + store in webhook data |
| `from_embed_widget(config)` | Widget configuration | `store_slug` from widget params |
| `from_admin_session(user_id)` | Admin dashboard | User-to-store assignment |
| `from_slug(slug)` | CLI / subdomain | `"electronics"` → registry lookup |
| `from_config(config)` | Raw dict | Direct TenantContext construction |

## Resolver Registry

Resolvers use an in-memory `store_registry` dict that maps store slugs to tenant configs:

```python
STORE_REGISTRY = {
    "electronics": {
        "organization_id": "org_elec_001",
        "store_id": "store_elec_001",
        "merchant_id": "merchant_elec_001",
        "integration_id": "int_elec_shopify",
        "store_slug": "electronics",
        "language": "en",
        "currency": "USD",
        "timezone": "America/New_York",
    },
    ...
}
```

## Enforcement Points

### 1. RetrieverService (`app/application/knowledge/retrieval/service.py`)

- **Constructor:** Accepts optional `tenant: TenantContext`
- **`_enforce_tenant_scope(filters)`:** Auto-injects `organization_id`, `store_id`, `knowledge_version` from tenant into every search filter
- **`_build_filter_conditions()`:** Always appends `document_status=active` unless explicitly overridden
- **`_collection_name()`:** Uses `tenant.collection_name` when a tenant is set

### 2. KnowledgeSyncCoordinator (`app/application/knowledge/coordinator.py`)

- Every operation is scoped to `tenant.organization_id` + `tenant.store_id`
- Version documents are stored with both IDs for per-store isolation
- Vector payloads include both IDs for Qdrant-level filtering
- Celery tasks pass org_id + store_id as arguments

### 3. ContextBuilder (`app/application/rag/context_builder.py`)

- All repository queries use tenant-scoped filters
- RetrieverService calls pass tenant IDs explicitly
- Knowledge version lookup filters by org_id + store_id

## Vector Payload Schema

Every vector in Qdrant includes these tenant isolation fields:

```json
{
  "organization_id": "org_elec_001",
  "store_id": "store_elec_001",
  "merchant_id": "merchant_elec_001",
  "document_status": "active",
  "knowledge_version": 1,
  "document_id": "...",
  "chunk_id": "...",
  "document_type": "upload",
  "source_type": "upload",
  "language": "en",
  "product_id": "...",
  "category_id": "...",
  "brand_id": "..."
}
```

## Verification

Run the playground with different stores to verify isolation:

```bash
python scripts/rag_playground.py --store electronics  # → Salla responses
python scripts/rag_playground.py --store fashion      # → Amazon Business responses
```

Each store returns answers from its own documents only. See `resources/testing/screenshots/` for recorded output.
