# Wished — Product Specification

Internal product and business rules reference. This is the canonical source of truth for product behavior, flows, and edge cases.

- Public overview: [README.md](../README.md)
- Infrastructure and ops: [INFRASTRUCTURE.md](./INFRASTRUCTURE.md)
- Agent coding rules: [AGENTS.md](../AGENTS.md)

---

## 1. Product Overview

Gift giving is often fragmented across chats, screenshots, notes, links, and last-minute guesses. People struggle to communicate what they actually want, while gift-givers struggle to choose meaningful gifts without duplicates, awkward coordination, or spoiled surprises.

Wished turns wishlists into a lightweight social experience inside Telegram, where gift planning already happens.

Primary goals:

- Let users authenticate with Telegram.
- Let users create profiles, wishlists, and wishes.
- Let users discover public profiles and public wishlists.
- Prevent duplicate gifting through reservations.
- Hide reservation details from the wish owner.
- Support group contributions toward a single wish.
- Track completed wishes.
- Notify users about relevant social and wishlist activity.

Non-goals for MVP:

- In-app payments.
- Marketplace checkout.
- Native mobile apps.
- Advanced recommendation systems.
- Complex public social networking.

---

## 2. Target Audience

- Telegram users who exchange gifts with people, families, communities, or colleagues.
- People maintaining wishlists for birthdays, holidays, weddings, baby showers, housewarmings, or personal milestones.
- Groups and families that coordinate gifts in chats.
- Creators or community leaders who may later share curated public wishlists.
- Small merchants or brands that may later participate through product discovery or affiliate links.

---

## 3. Core Features

- Telegram authentication.
- User profiles.
- Subscriptions to wishlist activity.
- Wishlist creation and management.
- Wish creation and management.
- Reservations to prevent duplicate gifts.
- Hidden reservations from wish owners.
- Group gifts — multiple contributors pooling money toward one wish.
- Completed wishes.
- In-app notifications.
- Optional media uploads backed by MinIO.

---

## 4. MVP Scope

MVP should support the smallest complete gift coordination loop:

1. A user opens Wished from Telegram.
2. The user signs in with Telegram.
3. The user has a profile.
4. The user creates a wishlist.
5. The user adds wishes.
6. The user makes the wishlist public.
7. Another user opens the profile and public wishlist.
8. The viewer reserves or copies a wish, or joins a group gift.
9. Other eligible viewers see the wish as unavailable.
10. The wish owner does not see reservation details.
11. The wish can be marked completed.
12. Users receive basic in-app notifications.

Included in MVP:

- Telegram Mini App launch and authentication.
- Basic user profile.
- Wishlist creation, editing, deletion, or archival.
- Wish creation, editing, deletion, or archival.
- Profile discovery and public profile viewing.
- Copying public wishes into owned wishlists.
- Public and private wishlist visibility.
- One active reservation per wish.
- Hidden reservation behavior from the wish owner.
- Group gifts with contribution tracking and transfer confirmation.
- Completed wish state.
- Basic in-app notifications.
- PostgreSQL-backed durable data.
- Redis for cache, rate limiting, sessions, or background coordination where needed.
- MinIO for user-uploaded media.

Excluded from MVP:

- Payments.
- Checkout.
- Price tracking.
- Store integrations.
- Advanced privacy controls.
- Blocking and reporting.
- Telegram bot notifications unless separately required.
- Admin dashboard unless separately required.
- Multi-language support unless separately required.

---

## 5. User Stories

### Authentication

- As a Telegram user, I want to sign in using Telegram so that I do not need a separate account.
- As a returning user, I want Wished to recognize me so that I can continue using my profile.
- As the system, I need to verify Telegram authentication server-side so that users cannot impersonate others.

### Profiles

- As a user, I want to create and edit my profile so that other users can recognize me.
- As a user, I want to view another user's profile so that I can see their available wishlists.

### Subscriptions

- As a user, I want to subscribe to wishlist activity so that I can receive updates.
- As a user, I want to unsubscribe so that I can reduce unwanted notifications.

### Wishlists and Wishes

- As a user, I want to create wishlists so that I can organize wishes by occasion or theme.
- As a user, I want to add wishes with useful details so that gift-givers can make informed decisions.
- As a viewer, I want to see wish details so that I can choose a gift.
- As a viewer, I want to copy a public wish into my own wishlist.

### Reservations

- As a viewer, I want to reserve a wish so that others know it is already planned.
- As a viewer, I want to cancel my reservation if I can no longer buy the gift.
- As the wish owner, I should not see who reserved my wish before completion or reveal.

### Group Gifts

- As a viewer, I want to start a group gift on a wish so others can contribute money toward it.
- As a contributor, I want to join an existing group gift and commit an amount.
- As a contributor, I want to report that I have transferred my share to the organizer.
- As the organizer, I want to confirm received transfers and track who has paid.
- As the organizer, I want to mark the group gift as purchased once the item is bought.
- As a contributor, I want to leave a group gift if I can no longer participate.

### Completed Wishes

- As a user, I want to mark a wish as completed so that my active wishlist stays current.
- As a user, I want completed wishes separated from active wishes.

### Notifications

- As a user, I want notifications about wishlist updates and allowed completion activity.
- As a user, I do not want notifications to spoil hidden reservations.

---

## 6. Business Rules

- A Telegram identity can belong to only one Wished account.
- Telegram identity must be validated by the backend.
- Users can modify only resources they own unless explicitly authorized.
- Users cannot subscribe to themselves unless product policy changes.
- Duplicate subscriptions must be prevented.
- A wishlist belongs to exactly one owner.
- A wish belongs to exactly one wishlist.
- Wishlists are ordered within each user's profile.
- Wishes are ordered within each wishlist.
- A completed, archived, or deleted wish cannot be reserved.
- A user cannot reserve their own wish unless product policy changes.
- MVP allows only one active reservation per wish.
- Reservation details must be hidden from the wish owner.
- Gift-givers may see that a wish is unavailable to prevent duplicate gifts.
- A wish may have one active group gift at a time.
- Only the group gift organizer may update payment details, confirm transfers, and mark the gift as purchased.
- The organizer may remove a contributor's contribution.
- A contributor may leave a group gift before the organizer marks it purchased.
- Notifications must be created only for users authorized to know about the event.
- Hidden reservation activity must not leak through notifications, counts, timestamps, sorting, or activity feeds.
- PostgreSQL is the source of truth for durable business state.
- Redis must not be the source of truth for reservations, users, wishlists, wishes, or notification history.

---

## 7. Edge Cases

- Telegram authentication data is missing, malformed, expired, or invalid.
- A Telegram user exists but local profile onboarding is incomplete.
- A user deletes a wishlist that contains active or reserved wishes.
- A user edits, deletes, or completes a reserved wish.
- A user edits or deletes a wish that has an active group gift.
- Two users try to reserve the same wish at nearly the same time.
- Wishlist visibility changes after a reservation or group gift exists.
- A wish owner views a wishlist after a hidden reservation occurs.
- A notification points to deleted or inaccessible content.
- A group gift contributor reports a transfer but the organizer disputes it.
- Media upload succeeds in MinIO but is never attached in PostgreSQL.
- Media metadata exists but the object is missing in MinIO.

---

## 8. Event Flow

Wished uses domain events for side effects, especially notifications.

General flow:

1. The frontend sends an authenticated request.
2. The backend validates authentication and authorization.
3. The domain module performs the operation inside a transaction when state changes.
4. The domain module records the state change.
5. A domain event is emitted after successful persistence.
6. Event handlers run synchronously or through a Redis-backed worker.
7. Notification handlers create recipient-specific notifications where allowed.
8. Frontend state is refreshed through server-state queries.

Initial event categories:

- Profile events.
- Subscription events.
- Wishlist events.
- Wish events.
- Reservation events.
- Group gift events.
- Completion events.
- Media events.

Events are for side effects. PostgreSQL remains the source of truth for business state.

---

## 9. Notification Flow

Notification creation flow:

1. A domain action occurs.
2. A domain event is emitted.
3. The notification module receives the event.
4. Candidate recipients are selected.
5. The policy module filters recipients by access and privacy.
6. Viewer-safe notification content is generated.
7. Notification records are stored.
8. The frontend fetches notifications and unread counts.

Notification privacy rules:

- New wishlist and new wish notifications may go only to subscribers with access.
- Reservation notifications must not go to the wish owner.
- Reservation confirmations may go to the reservation owner if product policy requires them.
- Notification text must not reveal hidden reservation owner, timestamp, notes, cancellation history, or indirect activity signals.

---

## 10. Reservation Flow

Reservation creation flow:

1. An authenticated user views an accessible wishlist.
2. The backend returns viewer-safe wish state.
3. The user requests to reserve a wish.
4. The backend verifies authentication.
5. The backend verifies the user can view the wish.
6. The backend verifies the user is not the wish owner.
7. The backend verifies the wish is active and not completed, archived, or deleted.
8. The backend verifies no active reservation already exists.
9. The backend creates the reservation inside a transaction.
10. The backend emits a reservation event.
11. Notification handling applies hidden reservation privacy rules.
12. The frontend refreshes the wish state.

Concurrency requirement:

- If two users try to reserve the same wish at the same time, only one reservation may succeed.
- The losing request should receive the project's standard conflict response.
- The frontend should refresh and show the wish as unavailable.

Wish owner privacy:

- The wish owner must not see who reserved the wish.
- The wish owner must not see reservation notes.
- The wish owner must not see reservation timestamps.
- The wish owner must not see cancellation history.
- The wish owner must not receive reservation notifications.

---

## 11. Group Gift Flow

Group gift creation flow:

1. An authenticated viewer opens an active, unreserved wish.
2. The viewer starts a group gift, setting a target amount and payment details.
3. Other viewers join by committing a contribution amount.
4. Each contributor reports their transfer to the organizer.
5. The organizer confirms or disputes each transfer.
6. When all contributions are confirmed, the organizer marks the gift as purchased.
7. The wish transitions to reserved/completed state.

Cancellation and removal:

- A contributor may leave before the gift is marked purchased.
- The organizer may remove a contributor's contribution at any time.
- If all contributors leave, the group gift is cancelled.

---

## 12. File Upload Flow

Recommended MVP upload flow:

1. An authenticated user selects a file.
2. The frontend asks the backend to start an upload.
3. The backend verifies authentication.
4. The backend verifies the target resource can be modified by the user.
5. The backend validates intended file type and size.
6. The backend creates pending media metadata.
7. The backend returns upload instructions.
8. The frontend uploads the object to MinIO using the approved instructions.
9. The frontend tells the backend the upload is complete.
10. The backend verifies the object exists in MinIO.
11. The backend marks the media as uploaded.
12. The backend attaches the media to the target resource.
13. The frontend refreshes the target resource.

Media lifecycle states: Pending → Uploaded → Attached → Failed → Deleted.

Upload rules:

- Only authenticated users may upload files.
- Users may attach media only to resources they can modify.
- File type and size must be validated.
- Object names must not expose sensitive user data.
- Orphaned pending uploads should be cleaned up.
- MinIO object storage is not the source of truth for media ownership.

---

## 13. Success Metrics

- Number of activated users who create at least one wishlist.
- Wishlist creation rate.
- Average number of items per wishlist.
- Share rate per wishlist.
- Shared wishlist open rate.
- Reservation rate for wishlist items.
- Group gift participation rate.
- Weekly and monthly active users.
- Retention after first wishlist creation.
- Number of Telegram chats or groups where wishlists are shared.
- Gift coordination completion rate for occasion-based wishlists.
