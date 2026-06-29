# Wished — AI Coding Agent Rules

Mandatory rules for AI coding agents working on Wished.
These rules are strict. If a required detail is missing, stop and ask before changing code.

**Sources of truth** (read docs before code):
- Product rules and business logic: `docs/PRODUCT.md`
- Infrastructure: `docs/INFRASTRUCTURE.md`
- This file: agent rules (mandatory)

---

## Architecture

### Backend: `backend/app/`

```
api/v1/{feature}/router.py  →  modules/{feature}/service.py  →  modules/{feature}/schemas.py
                                              ↓
                                    db/repositories/  →  db/models/  →  db/migrations/

core/config/      settings and env
core/security/    JWT, tokens
core/errors/      error handling patterns
integrations/     redis, minio, telegram
modules/          feature business logic (auth, wishlists, wishes, reservations, …)
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

## Domain Invariants

| Domain | Invariant |
|---|---|
| Auth | Telegram initData validated backend-side; `core/security/jwt.py` issues tokens |
| Wishlists | Owner-only writes; visibility enforced at service layer |
| Wishes | active → completed / archived / deleted; reserved wish has side effects on delete |
| Reservations | One active per wish; DB transaction; owner never sees reserver info |
| Group Gifts | One per wish; organizer controls payment details and confirms transfers; `modules/group_gifts/` |
| Discovery | Follow model: `db/models/follows.py`; privacy enforced server-side |
| Notifications | Never leak reservation metadata to wish owner |
| Media | MinIO stores bytes; PostgreSQL owns metadata and attachment state |

---

## Pre-Implementation Checklist

Before implementing a non-trivial task, state:

1. **Docs reviewed** — which files you read
2. **Affected files** — exact paths
3. **Edge cases** — cross-check with `docs/PRODUCT.md §7`
4. **Ordered plan**

Wait for approval on large changes before writing code.

---

## Skip These

`node_modules/`, `.next/`, `__pycache__/`, lock files, migration files (unless changing schema), unrelated features.

---

## 1. Project Rules

- Never invent database fields.
- Never invent APIs.
- Never invent routes.
- Never invent business logic.
- Never modify unrelated files.
- Never rewrite large areas without explicit need.
- Never make technical decisions that conflict with existing project documentation.
- Always follow the existing architecture.
- Always check documentation first.
- Always inspect existing code before editing.
- Always keep changes scoped to the requested task.
- Always preserve existing behavior unless the task explicitly requires changing it.
- Always ask when requirements are incomplete, ambiguous, or conflicting.
- If information is missing, STOP and ask.

---

## 2. Architecture Rules

- Follow the architecture already present in the repository.
- Do not introduce new architectural layers without explicit approval.
- Do not introduce new services without explicit approval.
- Do not introduce new frameworks without explicit approval.
- Do not move files across architectural boundaries unless the task explicitly requires it.
- Keep frontend, backend, database, infrastructure, and documentation concerns separate.
- Keep business rules in the established business logic location.
- Keep API transport concerns separate from persistence concerns.
- Keep Telegram-specific integration code in the established Telegram integration area.
- If the correct location for a change is unclear, STOP and ask.

---

## 3. Backend Rules

- Backend code uses FastAPI.
- Follow existing FastAPI application structure.
- Do not create endpoints that are not documented or requested.
- Do not change endpoint behavior without checking existing API contracts.
- Do not invent request models.
- Do not invent response models.
- Do not invent service methods.
- Do not bypass existing validation, authentication, or authorization patterns.
- Keep database access in the established persistence layer.
- Keep business logic out of route handlers unless the existing codebase already does otherwise.
- Handle errors through the existing error handling pattern.
- Do not expose internal exceptions or sensitive data in API responses.
- If backend behavior is not documented or discoverable in code, STOP and ask.

---

## 4. Frontend Rules

- Frontend code uses Next.js, TypeScript, Tailwind CSS, Telegram Mini Apps SDK, Zustand, and TanStack Query.
- Follow existing Next.js routing and component structure.
- Do not invent frontend routes.
- Do not invent API calls.
- Do not invent state fields.
- Do not introduce new state stores unless needed and consistent with existing patterns.
- Use TanStack Query for server state when the existing frontend pattern does so.
- Use Zustand only for local client state that belongs in a client store.
- Keep Telegram Mini App behavior consistent with the existing SDK integration.
- Do not hardcode backend URLs, Telegram configuration, secrets, or environment-specific values.
- Keep UI changes consistent with existing design patterns.
- Always translate all new user-facing strings to all 3 supported languages (en, ru, kz) in `frontend/src/lib/i18n/dict.ts`.
- If the intended UX is unclear, STOP and ask.

---

## 5. Database Rules

- PostgreSQL is the primary durable database.
- Never invent database fields.
- Never invent tables.
- Never invent relationships.
- Never invent indexes.
- Never invent enum values.
- Never modify migrations without understanding current schema state.
- Every schema change must be tied to an explicit requirement.
- Every schema change must include a migration.
- Do not edit historical migrations unless explicitly allowed and the migration has not been shared.
- Do not drop data, columns, tables, or constraints without explicit approval.
- Do not store secrets in the database unless an approved design requires it.
- If the data model is missing or unclear, STOP and ask.

---

## 6. API Rules

- Never invent APIs.
- Never invent routes.
- Never invent request payloads.
- Never invent response payloads.
- Never invent status codes.
- Follow existing API naming, versioning, authentication, and error response conventions.
- Keep API contracts stable unless the task explicitly requires a breaking change.
- Update API documentation when an API contract changes.
- Validate Telegram init data according to the established project pattern.
- Do not trust client-provided identity, ownership, or authorization claims.
- If an API contract is not defined, STOP and ask.

---

## 7. Docker Rules

- Docker is used for local and deployment infrastructure.
- Docker Compose is used for local service orchestration.
- Do not change exposed ports without explicit need.
- Do not change service names without explicit need.
- Do not remove volumes without explicit approval.
- Do not bake secrets into Dockerfiles, images, or Compose files.
- Keep development and production configuration concerns separate.
- PostgreSQL, Redis, and MinIO configuration must match documented environment variables.
- If Docker behavior is unclear or conflicts with documentation, STOP and ask.

---

## 8. Testing Rules

- Add or update tests for changed behavior.
- Do not delete tests to make a build pass.
- Do not weaken assertions unless the requirement changed.
- Backend tests must cover meaningful API, service, validation, and persistence behavior affected by the change.
- Frontend tests must cover meaningful user flows, rendering logic, state behavior, or API integration boundaries affected by the change.
- Run the relevant test suite before reporting completion when feasible.
- If tests cannot be run, report exactly why.
- If existing tests define behavior that conflicts with the request, STOP and ask.

---

## 9. Security Rules

- Never commit secrets.
- Never log secrets.
- Never expose Telegram bot tokens.
- Never trust Telegram client data without server-side validation.
- Never trust user ownership or permission claims from the client.
- Validate input at API boundaries.
- Enforce authorization on protected resources.
- Use environment variables for secrets and deployment-specific configuration.
- Keep CORS, cookies, sessions, and tokens consistent with documented security requirements.
- Do not weaken authentication, authorization, validation, rate limiting, or storage access rules without explicit approval.
- If a requested change creates a security risk, STOP and ask.

---

## 10. Code Style Rules

### General

- Prefer self-documenting code over comments.
- Maintain consistent style across frontend and backend.
- Well-named identifiers are better than a comment explaining them.

### Comments

Avoid unnecessary comments. Write one only when the **why** is non-obvious — a hidden constraint, a subtle invariant, a workaround for a specific bug, behavior that would surprise a reader.

When a comment is needed:

- Lowercase only
- No trailing punctuation
- Concise — explain intent, not implementation

Good:

```python
# telegram rejects requests older than 5 minutes
if age > 300:
    raise AuthError
```

Bad — states the obvious:

```python
# check if age is greater than 300
if age > 300:
    raise AuthError
```

Bad — wrong format:

```python
# Check if the Telegram init data has expired.
```

### Naming

Prefer descriptive names over comments.

Good: `user_profile_visibility`  
Bad: `upv`

### Prohibited

- Obvious comments
- Commented-out code
- TODO without an issue reference
- AI-generated banners
- Large comment blocks

---

## Security Checklist

Run before marking any task complete:

- [ ] No secrets in code, comments, or logs
- [ ] All protected endpoints verify ownership and auth
- [ ] Reservation response excludes owner-prohibited fields
- [ ] Input validated at API boundary (`api/v1/` routers)
- [ ] No CORS, cookie, or session rules weakened
- [ ] Telegram bot token not accessible to frontend or logged
