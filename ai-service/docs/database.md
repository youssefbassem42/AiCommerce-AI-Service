# Database

MongoDB is the primary data store. Qdrant handles vector search. Redis provides caching and session storage.

## MongoDB

### Connection

Configured via `MONGO_URI` and `MONGO_DB` environment variables. Uses Motor (async driver) with Beanie ODM.

### Collections

| Collection | Domain | Key Indexes |
|------------|--------|-------------|
| `products` | Commerce | `store_id`, `sku`, `category_id` |
| `categories` | Commerce | `store_id`, `parent_id` |
| `orders` | Commerce | `store_id`, `customer_id`, `order_number` |
| `customers` | Commerce | `store_id`, `email` |
| `inventory` | Commerce | `store_id`, `product_id`, `location` |
| `knowledge_documents` | Knowledge | `store_id`, `status`, `knowledge_version` |
| `knowledge_chunks` | Knowledge | `store_id`, `document_id` |
| `knowledge_versions` | Knowledge | `store_id`, `version` |
| `business_summaries` | Knowledge | `store_id` |
| `conversations` | Conversation | `store_id`, `user_id` |
| `tickets` | Ticket | `store_id`, `customer_id`, `status` |
| `api_keys` | Auth | `key_hash`, `store_id` |
| `audit_logs` | Auth | `store_id`, `user_id`, `timestamp` |
| `dashboard_insights` | Analytics | `store_id`, `metric`, `period` |
| `prompt_history` | Analytics | `store_id`, `timestamp` |
| `recommendations` | Recommendation | `store_id`, `user_id` |
| `bundle_suggestions` | Recommendation | `store_id` |

### Migrations

Run index creation:
```bash
python scripts/migrate_mongo.py
```

Index definitions are in `app/infrastructure/database/mongodb/indexes.py`.

## Qdrant

Vector store for knowledge chunks and product embeddings.
- Collections created per-store with `store_id` payload filter
- Payload indexes on `store_id`, `document_id`, `chunk_type`, `knowledge_version`

## Redis

- Celery broker and result backend
- Rate limiter counters
- Embedding cache (LRU with TTL)
- Session memory store (short-lived)
- API response cache (optional)
