# Wished Backend

FastAPI backend foundation for Wished.

Included:

- FastAPI application factory.
- Pydantic settings-based configuration.
- SQLAlchemy async PostgreSQL engine and session dependency.
- Alembic migration foundation.
- Redis async client dependency.
- Docker runtime support.
- Health endpoint.

## Local commands

Run the API locally from the repository root:

```bash
docker compose up --build backend
```

Run migrations when migration revisions exist:

```bash
docker compose exec backend alembic upgrade head
```

Health endpoint:

```text
GET /api/v1/health
```
