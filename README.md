# Wished

**Wished** is a Telegram Mini App for social wishlists and gift coordination. Create wishlists, share them with friends, and let people reserve or chip in on gifts — without spoiling surprises.

Built with Next.js, FastAPI, PostgreSQL, Redis, and the Telegram Mini Apps SDK.

---

## What it does

- **Wishlists** — create and manage wishlists by occasion or theme, set visibility to public or private
- **Wishes** — add wishes with titles, descriptions, links, and images
- **Reservations** — gift-givers can reserve a wish so others know it's taken; the wish owner never sees who reserved it
- **Group gifts** — multiple contributors can pool money toward a single wish; the organizer tracks contributions and confirms transfers
- **Discovery** — browse public profiles and wishlists from people you follow
- **Notifications** — in-app alerts for wishlist activity, respecting reservation privacy
- **Media uploads** — attach images to wishes via MinIO-backed object storage

---

## How it works

1. A user opens Wished from Telegram and authenticates with their Telegram identity.
2. They create a profile, a wishlist, and add wishes.
3. They make the wishlist public and share the link in a Telegram chat.
4. Another user opens the wishlist, reserves a wish or joins a group gift.
5. Other viewers see the wish as unavailable — the owner never sees reservation details.
6. The wish can be marked completed when the gift is given.

---

## Business rules

- Telegram identity is validated server-side on every authenticated request.
- One active reservation per wish. Concurrent reserve attempts are handled with a DB transaction and unique constraint.
- Reservation details (who, when, notes) are never exposed to the wish owner — not in responses, notifications, sort order, or counts.
- A wish owner cannot reserve their own wish.
- A completed, archived, or deleted wish cannot be reserved.
- Group gift contributions require explicit transfer confirmation from the organizer.
- PostgreSQL is the source of truth. Redis and MinIO are supporting infrastructure.

---

## Edge cases

- Telegram authentication data is missing, malformed, expired, or invalid.
- A user deletes a wishlist that contains active or reserved wishes.
- Two users try to reserve the same wish simultaneously.
- A wish is edited or deleted while a group gift is active.
- Media upload succeeds in MinIO but is never confirmed in PostgreSQL.
- A notification points to deleted or inaccessible content.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, TanStack Query, Zustand |
| Bot & Mini App | Telegram Mini Apps SDK, aiogram |
| Backend | FastAPI, Python |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Cache | Redis |
| Object storage | MinIO |
| Runtime | Docker Compose, Caddy |

---

## Project structure

```
wished/
  backend/        FastAPI backend
  frontend/       Next.js Mini App
  docs/           Product and infrastructure documentation
  scripts/        Local utility scripts
  infra/          Runtime infrastructure config
  deploy/         Production deployment scripts
  docker/         Dockerfiles
  tests/          Cross-project test suites
  .github/        CI/CD workflows
```

Backend code layout and agent coding rules: [AGENTS.md](./AGENTS.md)  
Infrastructure, setup, and deployment: [docs/INFRASTRUCTURE.md](./docs/INFRASTRUCTURE.md)

---

## Local development

**Prerequisites:** Docker, Docker Compose, a Telegram bot token from [@BotFather](https://t.me/BotFather)

```bash
cp .env.example .env
# fill in BOT_TOKEN and other required values

docker compose -f docker/docker-compose.yml up -d
```

**Enable inline sharing:** in [@BotFather](https://t.me/BotFather) run `/setinline` for your bot to turn on inline mode (any placeholder text works). This powers the clean "Share wishlist" flow; without it the app automatically falls back to the classic share sheet.

See [docs/INFRASTRUCTURE.md](./docs/INFRASTRUCTURE.md) for full setup, environment variables, and production deployment.
