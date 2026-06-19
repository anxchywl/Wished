# Wished

## Source of Truth

- Product rules and business logic: `README.md`
- Infrastructure: `INFRASTRUCTURE.md`
- Agent rules (mandatory): `AGENTS.md` — read before writing any code

This file is quick-reference only. When it conflicts with the above, those docs win.

Read docs before code. Read only files the task requires.

---

## Architecture

### Backend: `backend/app/`

```
api/v1/{feature}/router.py  →  {feature}/service.py  →  {feature}/schemas.py
                                        ↓
                              db/repositories/  →  db/models/  →  db/migrations/

core/config/      settings and env
core/security/    JWT, tokens
core/errors/      error handling patterns
integrations/     redis, minio, telegram
workers/          background tasks (bot.py)
```

### Frontend: `frontend/src/`

```
app/{route}/page.tsx          Next.js routes
features/{feature}/
  api.ts                      fetch calls
  hooks.ts                    TanStack Query hooks
  *-manager.tsx               page-level components
stores/                       Zustand — local client state only
lib/i18n/dict.ts              all user-facing strings
lib/telegram/                 Telegram SDK wrappers
```

Data flow: `Route → Component → TanStack Query hook → API client → Backend`

---

## Rules

**Never invent** fields, tables, routes, APIs, schemas, or business logic not in docs or existing code.

**Security:**
- Validate Telegram `initData` server-side on every authenticated request
- Never trust client identity, ownership, or permission claims
- Authorize ownership at the service layer, not just the route
- Never expose reservation details to the wish owner — not in responses, notifications, sort order, or counts
- Never commit secrets — use env vars, see `.env.example`
- Never log secrets or Telegram bot tokens

**Data:**
- PostgreSQL is source of truth — Redis and MinIO are not
- Reservation creation requires a DB transaction and unique constraint (one active per wish)
- Every schema change requires a migration in `db/migrations/versions/`

**i18n:** Every new user-facing string goes in `frontend/src/lib/i18n/dict.ts` with `en`, `ru`, and `kz` keys.

**When blocked:** If requirements are incomplete, ambiguous, or conflicting — stop and ask. Do not invent.

---

## Domain Invariants

| Domain | Invariant |
|---|---|
| Auth | Telegram initData validated backend-side; `core/security/jwt.py` issues tokens |
| Wishlists | Owner-only writes; visibility enforced at service layer |
| Wishes | active → completed / archived / deleted; reserved wish has side effects on delete |
| Reservations | One active per wish; DB transaction; owner never sees reserver info |
| Discovery | Follow model: `db/models/follows.py`; privacy enforced server-side |
| Notifications | Never leak reservation metadata to wish owner |
| Media | MinIO stores bytes; PostgreSQL owns metadata and attachment state |

---

## Workflow

Before implementing a non-trivial task, state:

1. **Docs reviewed** — which files you read
2. **Affected files** — exact paths
3. **Edge cases** — cross-check with `README.md §7`
4. **Ordered plan**

Wait for approval on large changes before writing code.

---

## Skip These

`node_modules/`, `.next/`, `__pycache__/`, lock files, migration files (unless changing schema), unrelated features.

---

## Security Checklist

- [ ] No secrets in code, comments, or logs
- [ ] All protected endpoints verify ownership and auth
- [ ] Reservation response excludes owner-prohibited fields
- [ ] Input validated at API boundary (`api/v1/` routers)
- [ ] No CORS, cookie, or session rules weakened
- [ ] Telegram bot token not accessible to frontend or logged
