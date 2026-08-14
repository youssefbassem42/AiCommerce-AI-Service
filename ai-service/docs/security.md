# Security

## Authentication

### JWT Tokens
- Signed with HMAC-SHA256 (`JWT_SECRET_KEY`)
- Refresh token rotation with token family tracking
- Security stamp validation for immediate invalidation

### API Keys
- Stored as SHA-256 hashes in MongoDB
- Scoped to individual stores
- Used for server-to-server integration auth

## Encryption

### Fernet (Symmetric)
- Used for encrypting integration credentials (OAuth tokens, webhook secrets)
- Key from `ENCRYPTION_KEY` environment variable
- Implemented in `app/infrastructure/security/encryption.py`

### JWKS
- Public/private key pairs for external service authentication
- Managed in `app/infrastructure/security/key_manager.py`

## Environment Variables

⚠️ **Never commit `.env` to version control**.

Required variables are validated at startup. Missing keys produce warnings in logs.

Key management recommendations:
- Development: `.env` file (excluded in `.gitignore`)
- Production: Secret manager (AWS Secrets Manager, HashiCorp Vault, Kubernetes Secrets)
- CI: Repository secrets / environment variables

## Rate Limiting

Endpoint-aware tiers (per identity, per minute):

| Tier | Applies to | Identity | Default limit |
|---|---|---|---|
| default | all non-whitelisted routes | JWT `store_id` claim, else client IP | 100 |
| llm | `/chat`, `/api/v1/ai/chat*`, `/rag/chat*`, `/api/v1/recommendations/*`, `/api/v1/widget/chat`, `/api/v1/widget/recommendations` | `store_id` claim, else client IP | 20 |
| widget_session | `/api/v1/widget/chat`, `/api/v1/widget/recommendations` | widget session store | 60 |
| widget_bootstrap | `/api/v1/widget/bootstrap` | SHA-256 hash of `X-Widget-Key` (raw key never stored/logged) | 30 |

- A request is counted against every tier it matches; the first tier to trip returns 429 with `tier`, `limit`, `reset_seconds` and `Retry-After`.
- Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (default tier), `X-RateLimit-Tier` on 429.
- Redis is the primary store; falls back to a bounded in-memory sliding window if Redis is unavailable.
- Limits configured via `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_LLM_PER_MINUTE`, `RATE_LIMIT_WIDGET_BOOTSTRAP_PER_MINUTE`, `RATE_LIMIT_WIDGET_SESSION_PER_MINUTE`.
- `/health` and `/health/` are whitelisted.

## Audit Logging

Every API request is logged with:
- User ID and store ID
- Action and resource
- IP address and user agent
- Request metadata (correlation ID, timestamp)

## Tenant Isolation

All data queries are tenant-scoped via `TenantContext`:
- MongoDB queries include `store_id` filter
- Qdrant searches use payload filters
- Business summaries are per-store

## Secrets Rotation

When rotating secrets:
1. Update the environment variable
2. Restart the service
3. For encryption keys, re-encrypt existing data with the new key
