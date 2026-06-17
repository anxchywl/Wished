# Wished Infrastructure Architecture

## 1. Services

Wished infrastructure is composed of the following services:

- **Telegram Mini App frontend**: User-facing web application loaded inside Telegram.
- **Next.js application**: Frontend application serving Mini App pages and client assets.
- **FastAPI backend**: Backend API for application logic, data access, Telegram validation, and integration workflows.
- **PostgreSQL**: Primary durable relational database.
- **Redis**: Cache, ephemeral state store, rate limiting support, and background coordination layer.
- **MinIO**: S3-compatible object storage for uploaded media and local object storage parity.
- **Reverse proxy / edge layer**: Public HTTP entry point for frontend and backend traffic in production.
- **Backup service**: Scheduled backup process for PostgreSQL and MinIO data.
- **Monitoring and logging layer**: Operational visibility for health, errors, resource usage, and audit trails.

## 2. Containers

Expected container responsibilities:

- **frontend**
  - Runs the Next.js application.
  - Serves Telegram Mini App frontend routes.
  - Communicates with the backend API through configured public or internal API URLs.

- **backend**
  - Runs the FastAPI application.
  - Validates Telegram Mini App init data.
  - Exposes API endpoints for the frontend.
  - Connects to PostgreSQL, Redis, and MinIO.

- **postgres**
  - Runs PostgreSQL.
  - Stores persistent relational data.
  - Uses a dedicated persistent volume.

- **redis**
  - Runs Redis.
  - Stores cache and ephemeral coordination data.
  - May use persistence depending on production requirements.

- **minio**
  - Runs MinIO object storage.
  - Stores uploaded media and object assets.
  - Uses a dedicated persistent volume.

- **minio-init**
  - Optional one-time setup container.
  - Creates required buckets and storage policies.
  - Runs only during initialization or deployment setup.

- **proxy**
  - Terminates or forwards HTTP traffic depending on deployment model.
  - Routes public requests to frontend and backend services.
  - Handles TLS in self-hosted production setups unless TLS is terminated upstream.

- **backup**
  - Runs scheduled backup jobs.
  - Exports PostgreSQL backups.
  - Syncs MinIO bucket data or snapshots object storage.
  - Sends backups to external storage.

## 3. Network Layout

The infrastructure should use separated network zones:

- **Public network**
  - Exposes only the reverse proxy or public application entry point.
  - Receives Telegram Mini App browser traffic.
  - Receives API requests from the frontend.

- **Application network**
  - Connects frontend and backend services.
  - Allows the proxy to route traffic to frontend and backend.
  - Not directly exposed to the public internet.

- **Data network**
  - Connects backend to PostgreSQL, Redis, and MinIO.
  - Isolated from public traffic.
  - Database, Redis, and MinIO ports should not be publicly exposed in production.

Traffic flow:

1. Telegram opens the Mini App URL.
2. User traffic reaches the public HTTPS endpoint.
3. The proxy routes frontend requests to Next.js.
4. The frontend calls the backend API.
5. The backend validates Telegram data and handles application requests.
6. The backend reads and writes PostgreSQL data.
7. The backend uses Redis for cache or ephemeral coordination.
8. The backend stores and retrieves media through MinIO.

## 4. Environment Variables

Environment variables should be grouped by responsibility.

### Frontend

- Public frontend URL.
- Public backend API URL.
- Telegram Mini App identifier or public configuration.
- Runtime environment.
- Feature flags, if used.

### Backend

- Backend public URL.
- Allowed frontend origins.
- Runtime environment.
- Application secret.
- Telegram bot token.
- Telegram init data validation configuration.
- Database connection settings.
- Redis connection settings.
- MinIO connection settings.
- Logging level.
- Rate limit configuration, if used.

### PostgreSQL

- Database name.
- Database user.
- Database password.
- Database host.
- Database port.
- Database connection URL.

### Redis

- Redis host.
- Redis port.
- Redis password, if enabled.
- Redis connection URL.
- Redis persistence mode, if configured.

### MinIO

- MinIO endpoint.
- MinIO public endpoint, if different.
- Access key.
- Secret key.
- Bucket names.
- Region, if required by S3-compatible clients.
- Presigned URL expiration settings.

### Proxy

- Public domain.
- TLS certificate configuration.
- Frontend upstream.
- Backend upstream.
- Request size limits.
- Timeout settings.

### Backup

- Backup schedule.
- Backup retention period.
- Backup destination.
- Backup encryption key or credentials.
- PostgreSQL backup configuration.
- MinIO backup configuration.

## 5. Storage Structure

Storage should be separated by data type and lifecycle.

### PostgreSQL Storage

- Application relational data.
- User records.
- Wishlist records.
- Wishlist item records.
- Reservation or coordination records.
- Audit or event data only if explicitly required by product design.

Database storage must be persistent and backed up regularly.

### Redis Storage

- Cache entries.
- Ephemeral workflow state.
- Rate limit counters.
- Background coordination data.

Redis should not be the only source of truth for critical business data.

### MinIO Storage

Recommended bucket separation:

- **wished-media**
  - User-uploaded wishlist item images.
  - Profile or wishlist media if supported.

- **wished-system**
  - Internal generated assets if needed.
  - Non-public system objects.

- **wished-backups**
  - Optional local backup staging bucket for development only.
  - Production backups should be copied to external durable storage.

Object paths should be predictable, scoped by entity type, and avoid exposing sensitive identifiers unnecessarily.

## 6. Volumes

Required persistent volumes:

- **postgres-data**
  - Stores PostgreSQL database files.
  - Must be backed up.

- **redis-data**
  - Stores Redis persistence files if Redis persistence is enabled.
  - Optional for purely ephemeral Redis usage.

- **minio-data**
  - Stores MinIO object data.
  - Must be backed up.

- **backup-data**
  - Temporary local backup staging area.
  - Should not be the only backup location.

Optional volumes:

- **proxy-certs**
  - Stores TLS certificates for self-hosted production.

- **proxy-logs**
  - Stores proxy logs if logs are file-based.

- **app-logs**
  - Stores application logs if logs are file-based.
  - Prefer centralized logging in production.

## 7. Backup Strategy

### PostgreSQL

- Run scheduled logical backups.
- Store backups outside the application host.
- Encrypt backups before or during transfer.
- Retain multiple restore points.
- Test restore procedures regularly.
- Keep backup retention aligned with business and compliance requirements.

Recommended backup tiers:

- Frequent short-retention backups for operational recovery.
- Daily medium-retention backups.
- Longer-retention backups for disaster recovery.

### MinIO

- Back up buckets through object replication, snapshotting, or scheduled sync.
- Store production object backups in external durable storage.
- Preserve metadata needed by the application.
- Include bucket policy and lifecycle configuration in infrastructure documentation.

### Redis

- Back up Redis only if it contains data that must survive restarts.
- If Redis is strictly ephemeral, prioritize fast recreation over backup.

### Verification

- Backups are not valid until restore has been tested.
- Restore testing should include PostgreSQL and MinIO together to confirm data consistency.
- Document recovery time objective and recovery point objective once business requirements are known.

## 8. Development Setup

Development infrastructure should prioritize reproducibility and low setup cost.

Development services:

- Next.js frontend container or local frontend process.
- FastAPI backend container or local backend process.
- PostgreSQL container.
- Redis container.
- MinIO container.
- Optional MinIO initialization container.

Development expectations:

- Use Docker Compose for shared infrastructure.
- Use local environment files excluded from Git.
- Provide an example environment file with non-secret placeholders.
- Expose service ports only for local development needs.
- Persist PostgreSQL and MinIO data across container restarts.
- Allow easy reset of local volumes when a clean environment is needed.
- Keep Telegram local testing requirements documented.
- Use HTTPS tunneling or an approved public development URL when Telegram requires a public Mini App endpoint.

Development data:

- Use seed data only when explicitly defined.
- Do not use production credentials.
- Do not connect local development to production databases, Redis, or object storage.

## 9. Production Setup

Production infrastructure should prioritize security, durability, observability, and controlled deployment.

Production services:

- Public reverse proxy or managed edge service.
- Next.js frontend runtime.
- FastAPI backend runtime.
- Managed or self-hosted PostgreSQL.
- Managed or self-hosted Redis.
- Managed object storage or hardened MinIO deployment.
- Backup runner or managed backup service.
- Monitoring, logging, and alerting stack.

Production requirements:

- Serve Telegram Mini App over HTTPS.
- Keep database, Redis, and MinIO private.
- Store secrets in a secure secret manager or protected deployment environment.
- Run database migrations through a controlled release process.
- Configure health checks for frontend, backend, PostgreSQL, Redis, and MinIO.
- Configure centralized logging for application and infrastructure services.
- Monitor API latency, error rates, container health, database performance, Redis memory, and object storage usage.
- Apply least-privilege access for MinIO buckets and service credentials.
- Use separate environments for development, staging, and production.
- Avoid sharing credentials across environments.
- Define a rollback process for application releases.
- Define a disaster recovery process for data restoration.

Production deployment topology may start as a single Docker Compose host for early-stage operation, but should be designed so PostgreSQL, Redis, object storage, and application services can later be migrated to managed or independently scaled infrastructure.

