# Wished Disaster Recovery

## Objectives

| Metric | Target |
|--------|--------|
| RPO (Recovery Point Objective) | ≤ 6 hours (backup interval) |
| RTO (Recovery Time Objective) | ≤ 2 hours |

---

## Backup Architecture

```
PostgreSQL ──► pg_dump (custom format, compressed)
                    │
                    ▼
MinIO ──────► mc mirror
                    │
                    ▼
             /var/backups/wished/{timestamp}/    ← host path, NOT a Docker volume
                    │
                    ▼ (if BACKUP_EXTERNAL_ENABLED=true)
             External S3-compatible bucket       ← survives server loss
```

**Critical design decision:** Backups land on a **host bind-mounted path** (`/var/backups/wished`), not a named Docker volume. This means `docker compose down -v`, `docker volume rm`, and `docker system prune -a` cannot destroy local backups.

---

## Backup Contents

Each timestamped backup directory contains:

```
/var/backups/wished/
└── 2026-06-22_12-00/
    ├── postgres.dump       pg_dump custom format, compressed
    ├── manifest.json       metadata for verification
    └── minio/
        ├── wished-media/   user-uploaded images
        └── wished-system/  system objects
```

---

## Common Failure Scenarios

### Scenario 1: `docker compose down -v` run accidentally

**Impact:** All named Docker volumes deleted — PostgreSQL data, MinIO data, Redis data.

**Recovery:**
- Local backups in `/var/backups/wished` survive (host path, not a volume).
- If external backup is configured, off-server copy also survives.
- Proceed to [Full Restore](#full-restore-procedure).

### Scenario 2: `docker volume rm wished_postgres-data`

**Impact:** PostgreSQL data lost.

**Recovery:** Same as Scenario 1.

### Scenario 3: Server lost / disk failure

**Impact:** Everything on the server is gone, including local backups.

**Recovery:**
- Requires external backup (`BACKUP_EXTERNAL_ENABLED=true`).
- Copy the latest backup from external S3 to the new server's `/var/backups/wished/`.
- Proceed to [Full Restore](#full-restore-procedure).

**If external backup was NOT configured:** data loss equals time since last off-server copy (manual export, if any).

### Scenario 4: Accidental data deletion (application level)

**Impact:** Rows deleted from database by operator or bug.

**Recovery:** Restore to a backup taken before the deletion. RPO = backup interval.

### Scenario 5: Bad migration applied

**Impact:** Schema change damaged or deleted user data.

**Recovery:**
1. Stop all application containers immediately.
2. Restore from the last backup taken before the migration.
3. Fix the migration before re-deploying.

---

## Full Restore Procedure

### Prerequisites

- Access to the server or a new server with Docker and Docker Compose.
- A valid backup in `/var/backups/wished/` (or downloaded from external storage).
- Production `.env` file with correct credentials.

### Step 1 — Stop application services

```bash
docker compose -f docker-compose.prod.yml stop backend frontend bot caddy
```

Do NOT use `down -v`. Keep database and MinIO containers running for the restore.

### Step 2 — Verify backup exists and is valid

```bash
docker compose -f docker-compose.prod.yml run --rm backup verify-backup
```

Note the timestamp of the backup that will be restored.

### Step 3 — Restore PostgreSQL and MinIO

Run interactively — the script will ask you to type `RESTORE` to confirm before dropping the database:

```bash
docker compose -f docker-compose.prod.yml run --rm backup restore latest
```

Or specify a timestamp:

```bash
docker compose -f docker-compose.prod.yml run --rm backup restore 2026-06-22_12-00
```

### Step 4 — Run pending migrations (if any)

If restoring from an older backup that predates recent migrations:

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

### Step 5 — Restart all services

```bash
bash scripts/deploy.sh
```

### Step 6 — Verify application health

```bash
docker compose -f docker-compose.prod.yml ps
curl -f https://your-domain/api/v1/health
```

---

## Restore from External Storage

If the server is lost and external backup is configured:

```bash
# On the new server, pull the backup down with mc
mc alias set external https://s3.example.com ACCESS_KEY SECRET_KEY
mc mirror external/wished-backups/2026-06-22_12-00/ /var/backups/wished/2026-06-22_12-00/

# Then proceed from Step 2 above
```

---

## Backup Verification (Routine)

Run weekly or after any infrastructure change:

```bash
docker compose -f docker-compose.prod.yml run --rm backup verify-backup
```

This checks:
- A recent backup exists.
- The PostgreSQL dump is structurally valid (`pg_restore --list`).
- The backup age is within the expected interval.

A backup that has never been verified is considered unverified.

---

## Safe Deployment

Always use the deployment script — it never removes volumes:

```bash
bash scripts/deploy.sh
```

**Never run:**
```bash
docker compose down -v          # destroys all volumes
docker volume rm wished_*       # destroys named volumes
docker system prune -a -f       # destroys everything including volumes
```

---

## Migration Safety

Before applying migrations to production:

```bash
bash scripts/check-migrations.sh
```

This scans for `drop_table`, `drop_column`, `TRUNCATE`, and mass `DELETE` operations. Destructive migrations require explicit human review — the script exits non-zero unless `FORCE_DESTRUCTIVE=true`.

---

## Contacts and Escalation

Fill in before going to production:

| Role | Contact |
|------|---------|
| On-call engineer | — |
| Database owner | — |
| Infrastructure owner | — |
