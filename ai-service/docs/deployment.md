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
