# AGENTS.md

# Wished AI Coding Agent Rules

This document defines mandatory rules for AI coding agents working on Wished.

These rules are strict. If a required detail is missing, stop and ask before changing code.

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

## 4. Frontend Rules

- Frontend code uses Next.js, TypeScript, Tailwind CSS, Telegram Mini Apps SDK, Zustand, and Tanstack Query.
- Follow existing Next.js routing and component structure.
- Do not invent frontend routes.
- Do not invent API calls.
- Do not invent state fields.
- Do not introduce new state stores unless needed and consistent with existing patterns.
- Use Tanstack Query for server state when the existing frontend pattern does so.
- Use Zustand only for local client state that belongs in a client store.
- Keep Telegram Mini App behavior consistent with the existing SDK integration.
- Do not hardcode backend URLs, Telegram configuration, secrets, or environment-specific values.
- Keep UI changes consistent with existing design patterns.
- Always translate all new user-facing functionality and text strings to all 3 supported languages (en, ru, kz) in the translation dictionary.
- If the intended UX is unclear, STOP and ask.

## 5. Database Rules

- PostgreSQL is the primary durable database.
- Never invent database fields.
- Never invent tables.
- Never invent relationships.
- Never invent indexes.
- Never invent enum values.
- Never modify migrations without understanding current schema state.
- Every schema change must be tied to an explicit requirement.
- Every schema change must include a migration if the project uses migrations.
- Do not edit historical migrations unless the project explicitly allows it and the migration has not been shared.
- Do not drop data, columns, tables, or constraints without explicit approval.
- Do not store secrets in the database unless an approved design requires it.
- If the data model is missing or unclear, STOP and ask.

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

## 8. Testing Rules

- Add or update tests for changed behavior.
- Do not delete tests to make a build pass.
- Do not weaken assertions unless the requirement changed.
- Backend tests must cover meaningful API, service, validation, and persistence behavior affected by the change.
- Frontend tests must cover meaningful user flows, rendering logic, state behavior, or API integration boundaries affected by the change.
- Run the relevant test suite before reporting completion when feasible.
- If tests cannot be run, report exactly why.
- If existing tests define behavior that conflicts with the request, STOP and ask.

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

## 10. Code Style and Documentation Rules

These rules are mandatory across the entire codebase.

General principles:

- Code should be self-documenting whenever possible.
- Comments should explain why, not what.
- Avoid obvious comments.
- Maintain consistent style across frontend and backend.
- Every public module, class, function, hook, service, repository, and endpoint must have a short docstring or comment.
- All comments must be concise.

Comment style:

- Use lowercase only.
- Never end comments with punctuation.
- Keep comments under six words when possible.

Good:

```python
# create jwt token pair
```

Bad:

```python
# Create JWT Token Pair.
```

Bad:

```python
# this function creates a jwt token pair for the user and returns both access and refresh tokens.
```

File headers:

- Every important file should start with a short header.

Examples:

```python
# authentication service
```

```typescript
// wishlist api client
```

Functions:

- Every public function should have a short docstring.

Python:

```python
def create_tokens(user: User) -> TokenPair:
    """create jwt token pair"""
```

TypeScript:

```typescript
/**
 * create wishlist
 */
export async function createWishlist() {}
```

Classes:

- Every class should contain a short description.

Python:

```python
class AuthService:
    """authentication operations"""
```

TypeScript:

```typescript
/**
 * wishlist state manager
 */
export class WishlistStore {}
```

API routes:

- Every route should contain a short description.

```python
@router.get("/me")
async def get_me():
    """get current profile"""
```

React components:

- Every exported component should contain a short description.

```typescript
/**
 * profile settings page
 */
export function ProfileSettingsPage() {}
```

Hooks:

- Every custom hook should contain a short description.

```typescript
/**
 * load current profile
 */
export function useProfile() {}
```

Services:

- Every service method should contain a short description.

```python
def update_profile():
    """update profile settings"""
```

Repositories:

- Every repository method should contain a short description.

```python
def get_by_telegram_id():
    """find user by telegram id"""
```

Migrations:

- Every migration must include a short description.

```python
"""add profile visibility fields"""
```

Prohibited comments:

- Obvious comments.
- Joke comments.
- Temporary comments.
- Commented-out code.
- TODO without an issue reference.
- AI generated banners.
- Large comment blocks.

Bad:

```python
# increment i by one
i += 1
```

Bad:

```python
# magic happens here
```

Naming:

- Prefer descriptive names over comments.

Good:

```python
user_profile_visibility
```

Bad:

```python
upv
```

Consistency:

- All generated code must follow these rules.
- If unsure, use fewer comments.
- If unsure, keep comments lowercase.
- If unsure, keep comments under six words.
- If unsure, never end comments with punctuation.
