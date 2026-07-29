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

- Per-store rate limiting via Redis
- Falls back to in-memory if Redis is unavailable
- Configurable limit (default: 100 requests/minute)

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
