# Deployment

## Docker (Recommended)

```bash
make docker-build
make docker-up
```

This starts:
- `ai-service` — FastAPI on port 8000
- `celery-worker` — Async task processing
- `celery-beat` — Scheduled task triggers
- `mongodb` — Data store on port 27017
- `redis` — Cache/broker on port 6379
- `qdrant` — Vector store on port 6333

### Environment

Set via `.env` file or environment variables. See `.env.example` for all options.

## Production Requirements

| Component | Min Spec | Production Spec |
|-----------|----------|-----------------|
| AI Service | 2 CPU, 4GB RAM | 4+ CPU, 8GB+ RAM |
| MongoDB | 2 CPU, 4GB RAM | 4+ CPU, 8GB+ RAM, SSD |
| Redis | 1 CPU, 1GB RAM | 2+ CPU, 4GB+ RAM |
| Qdrant | 1 CPU, 2GB RAM | 4+ CPU, 8GB+ RAM, SSD |

## Scaling

- **Horizontal**: Run multiple `ai-service` replicas behind a load balancer
- **Workers**: Scale `celery-worker` replicas independently based on queue depth
- **Qdrant**: Use Qdrant Cloud for managed scaling
- **MongoDB**: Use Atlas or replica set for HA

## Monitoring

- Health endpoint: `GET /health/`
- Prometheus metrics (if enabled)
- Celery monitoring via Flower

## Backup

- MongoDB: `mongodump` or Atlas snapshots
- Qdrant: Snapshot API or storage volume backup
- Redis: RDB/AOF persistence (configured in docker-compose)

## Rollback Strategy

- **Application rollback**: Revert to the previous container image (`docker compose down && docker compose up -d --build` with a pinned previous tag). API compat is guaranteed by the OpenAPI baseline (`docs/api/openapi-baseline.json`) — before upgrading, diff the deployed schema against the baseline; any UNINTENTIONAL BREAKING change blocks release.
- **Data safety**: No application phase (A–E, G) introduces schema changes, indexes, or data migrations. Rolling back the app never requires Mongo/Qdrant/Redis rollback.
- **Feature toggles**: Rate-limit tiers and limits are env-configurable (`RATE_LIMIT_*`); the widget AI-execution policy is bounded by `WidgetServerPolicy` defaults in code. Both can be relaxed without redeploying the container (env change + restart).
- **External services**: Mongo/Redis/Qdrant failures are designed to be controlled (in-flight fallbacks, empty retrieval results, error statuses) and never bypass tenant isolation — see `docs/audit/phase-g-report.md` §G4.
