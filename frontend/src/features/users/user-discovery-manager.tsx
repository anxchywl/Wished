"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useIsMutating } from "@tanstack/react-query";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
  defaultDropAnimationSideEffects,
  DragStartEvent,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { PublicWishlistNavigator } from "@/features/users/public-wishlist-navigator";
import { UserAvatar } from "@/features/users/user-avatar";
import {
  useFollowingQuery,
  useReorderFollowingMutation,
} from "@/features/users/hooks";
import {
  useBookedWishesQuery,
  useCancelReservationMutation,
  useReorderBookedWishesMutation,
  useReorderFulfilledWishesMutation,
} from "@/features/reservations/hooks";
import { useGroupGiftQuery } from "@/features/group-gifts/hooks";
import { ViewGroupGiftContent, type ActionMode } from "@/features/group-gifts/view-group-gift-sheet";
import { useProfileQuery, useUpdatePrivacyMutation } from "@/features/profile/hooks";
import { ProfileLinkShareCard } from "@/features/profile";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { logStartup } from "@/lib/debug/startup-log";
import { isAuthFailure, isAuthPending, useAuthStore } from "@/stores/auth-store";
import { useRouter, useSearchParams } from "next/navigation";
import type { BookedWishItem, FulfilledWishItem } from "@/features/reservations/api";
import type { FollowedUserResponse } from "@/features/users/api";
import { WishImageThumb } from "@/features/wishlists/wishlist-visuals";

/**
 * booking visibility header button — rendered in the cover header
 */
export function BookingVisibilityHeaderButton() {
  const { t } = useTranslation();
  const accessToken = useAuthStore((state) => state.accessToken);
  const profileQuery = useProfileQuery(accessToken);
  const updatePrivacy = useUpdatePrivacyMutation();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(false);

  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => setActive(true));
    } else {
      setActive(false);
    }
  }, [open]);

  const currentVisibility =
    (profileQuery.data?.privacy?.booking_visibility as BookingVisibility | undefined) ?? "hide";
  const currentGroupGiftVisibility =
    (profileQuery.data?.privacy?.group_gift_visibility as BookingVisibility | undefined) ?? "hide";

  function handleChange(value: BookingVisibility) {
    // close optimistically — onMutate already updates the profile cache
    setActive(false);
    window.setTimeout(() => setOpen(false), 340);
    updatePrivacy.mutate({ booking_visibility: value });
  }

  function handleGroupGiftChange(value: BookingVisibility) {
    setActive(false);
    window.setTimeout(() => setOpen(false), 340);
    updatePrivacy.mutate({ group_gift_visibility: value });
  }

  return (
    <>
      <button
        className="lang-toggle"
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Booking visibility"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>

      {open && typeof document !== "undefined" && createPortal(
        <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={() => setOpen(false)}>
          <div className={`modal-sheet ${active ? "visible" : ""}`} onClick={(e) => e.stopPropagation()}>
            <div className="modal-handle" />
            <h3 className="modal-title font-bold text-sm mb-2 text-center">{t("bookingVisibilityTitle")}</h3>
            <div className="flex flex-col gap-1.5">
              {(["hide", "anonymous", "names"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`flex flex-col items-start px-3 py-2 rounded-lg border transition-all text-left ${
                    currentVisibility === option
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border bg-background text-foreground"
                  }`}
                  onClick={() => handleChange(option)}
                  disabled={updatePrivacy.isPending}
                >
                  <span className="text-xs font-bold">
                    {option === "hide"
                      ? t("bookingVisibilityHide")
                      : option === "anonymous"
                      ? t("bookingVisibilityAnonymous")
                      : t("bookingVisibilityNames")}
                  </span>
                  <span className="text-[11px] leading-snug text-muted mt-0.5">
                    {option === "hide"
                      ? t("bookingVisibilityHideDesc")
                      : option === "anonymous"
                      ? t("bookingVisibilityAnonymousDesc")
                      : t("bookingVisibilityNamesDesc")}
                  </span>
                </button>
              ))}
            </div>
            <h3 className="modal-title font-bold text-sm mt-3 mb-2 text-center">{t("groupGiftVisibilityTitle")}</h3>
            <div className="flex flex-col gap-1.5">
              {(["hide", "anonymous", "names"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`flex flex-col items-start px-3 py-2 rounded-lg border transition-all text-left ${
                    currentGroupGiftVisibility === option
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border bg-background text-foreground"
                  }`}
                  onClick={() => handleGroupGiftChange(option)}
                  disabled={updatePrivacy.isPending}
                >
                  <span className="text-xs font-bold">
                    {option === "hide"
                      ? t("groupGiftVisibilityHide")
                      : option === "anonymous"
                      ? t("groupGiftVisibilityAnonymous")
                      : t("groupGiftVisibilityNames")}
                  </span>
                  <span className="text-[11px] leading-snug text-muted mt-0.5">
                    {option === "hide"
                      ? t("groupGiftVisibilityHideDesc")
                      : option === "anonymous"
                      ? t("groupGiftVisibilityAnonymousDesc")
                      : t("groupGiftVisibilityNamesDesc")}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}

type TelegramWindow = Window & {
  Telegram?: {
    WebApp?: {
      close?: () => void;
      openTelegramLink?: (url: string) => void;
    };
  };
};

type BookingVisibility = "hide" | "anonymous" | "names";

/**
 * discover telegram contacts
 */
export function UserDiscoveryManager() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedUsername = searchParams.get("profile");
  const selectedPublicUsername = searchParams.get("profile_public");
  const selectedUserId = searchParams.get("profile_id");
  const profileToken = searchParams.get("profile_token");
  const selectedWishlistId = searchParams.get("wishlist");
  const selectedWishId = searchParams.get("wish");
  const shareToken = searchParams.get("share_token");
  const followingQuery = useFollowingQuery();
  const followedUsers = followingQuery.data?.items ?? [];
  const bookedWishesQuery = useBookedWishesQuery();
  const profileQuery = useProfileQuery(accessToken);
  const bookedWishes = bookedWishesQuery.data?.items ?? [];
  const fulfilledWishes = bookedWishesQuery.data?.fulfilled_items ?? [];
  const { t } = useTranslation();

  const guardDecision = isAuthPending(authStatus)
    ? "startup"
    : isAuthFailure(authStatus) || (authStatus !== "authenticated" && !accessToken)
      ? "auth_required"
      : "app";

  logStartup("route guard decision", authStatus, {
    component: "UserDiscoveryManager",
    decision: guardDecision,
    hasAccessToken: Boolean(accessToken),
  });

  return (
    <>
      <main className="content discover-content">
        {guardDecision === "startup" ? (
          <AuthRequiredPanel forcePending />
        ) : guardDecision === "auth_required" ? (
          <AuthRequiredPanel />
        ) : (
          <>
          <ProfileLinkShareCard
            publicUsername={profileQuery.data?.public_username}
            publicProfileUrl={profileQuery.data?.public_profile_url}
            telegramStartappUrl={profileQuery.data?.telegram_startapp_url}
          />
          {followedUsers.length > 0 ? (
          <>
          <FriendsPanel items={followedUsers} />
          <BookedWishesPanel items={bookedWishes} />
          <FulfilledWishesPanel items={fulfilledWishes} />
          </>
        ) : (
          <>
          <BookedWishesPanel items={bookedWishes} />
          <FulfilledWishesPanel items={fulfilledWishes} />
          <section className={`discover-launch ${bookedWishes.length || fulfilledWishes.length ? "discover-launch-after-bookings" : ""}`}>
            <h2>{t("findTelegramFriends")}</h2>
            <button type="button" className="discover-launch-button" onClick={openTelegramFriendPicker}>
              <span>{t("chooseTelegramUsers")}</span>
            </button>
          </section>
          </>
        )}
          </>
        )}

      </main>

      <PublicWishlistNavigator
        open={Boolean(selectedUsername || selectedUserId || selectedPublicUsername)}
        username={selectedUsername}
        publicUsername={selectedPublicUsername}
        userId={selectedUserId}
        profileToken={profileToken}
        initialWishlistId={selectedWishlistId}
        initialWishId={selectedWishId}
        shareToken={shareToken}
        onClose={() => router.replace("/users")}
      />

    </>
  );
}

function useDiscoverDragSensors() {
  return useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        delay: 300,
        tolerance: 6,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
}

function usePreventScrollWhileDragging(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const preventScroll = (event: TouchEvent) => {
      event.preventDefault();
    };
    document.addEventListener("touchmove", preventScroll, { passive: false });
    return () => {
      document.removeEventListener("touchmove", preventScroll);
    };
  }, [active]);
}

function FriendsPanel({ items }: { items: FollowedUserResponse[] }) {
  const router = useRouter();
  const { t } = useTranslation();
  const sensors = useDiscoverDragSensors();
  const reorderMutation = useReorderFollowingMutation();
  const isReordering = useIsMutating({ mutationKey: ["reorderFollowing"] }) > 0;
  const [orderIds, setOrderIds] = useState<string[]>([]);
  const [activeUser, setActiveUser] = useState<FollowedUserResponse | null>(null);
  const users = useMemo(() => items, [items]);

  const resolvedOrderIds = useMemo(() => {
    if (orderIds.length === 0) return users.map((user) => user.user_id);
    return orderIds;
  }, [orderIds, users]);

  const orderedUsers = useMemo(() => {
    const byId = new Map(users.map((user) => [user.user_id, user]));
    const ordered = resolvedOrderIds
      .map((id) => byId.get(id))
      .filter((user): user is FollowedUserResponse => Boolean(user));
    const orderedIds = new Set(ordered.map((user) => user.user_id));
    return [...ordered, ...users.filter((user) => !orderedIds.has(user.user_id))];
  }, [users, resolvedOrderIds]);

  usePreventScrollWhileDragging(activeUser !== null);

  useEffect(() => {
    if (activeUser || reorderMutation.isPending || isReordering) return;
    const userIds = users.map((user) => user.user_id);
    setOrderIds((prev) => {
      if (prev.length === userIds.length && prev.every((id, index) => id === userIds[index])) {
        return prev;
      }
      return userIds;
    });
  }, [users, activeUser, reorderMutation.isPending, isReordering]);

  function handleDragStart(event: DragStartEvent) {
    const activeItem = users.find((user) => user.user_id === event.active.id);
    if (activeItem) setActiveUser(activeItem);
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const currentOrder = orderIds.length > 0 ? orderIds : resolvedOrderIds;
      const oldIndex = currentOrder.indexOf(active.id as string);
      const newIndex = currentOrder.indexOf(over.id as string);
      const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
      setOrderIds(newOrder);
      reorderMutation.mutate(
        { user_ids: newOrder },
        {
          onError: () => {
            setOrderIds(orderIds);
          },
        },
      );
    }
    setActiveUser(null);
  }

  return (
    <div className="panel discover-following-panel flex flex-col p-0 overflow-hidden bg-background w-full self-start" style={{ padding: 0 }}>
      <div className="px-4 py-3">
        <h3 className="text-sm font-bold text-foreground">{t("friends")}</h3>
      </div>
      <div className="mx-4 h-0.5 bg-border" />
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setActiveUser(null)}
      >
        <div className="discover-following">
          <SortableContext items={resolvedOrderIds} strategy={verticalListSortingStrategy}>
            {orderedUsers.map((user, index) => (
              <SortableFriendRow
                key={user.user_id}
                user={user}
                isLast={index === orderedUsers.length - 1}
                onOpen={() => {
                  router.replace(`/users?profile_id=${encodeURIComponent(user.user_id)}`);
                }}
              />
            ))}
          </SortableContext>
        </div>
        <DragOverlay
          dropAnimation={{
            sideEffects: defaultDropAnimationSideEffects({
              styles: { active: { opacity: "0.4" } },
            }),
          }}
        >
          {activeUser ? <FriendRowOverlay user={activeUser} /> : null}
        </DragOverlay>
      </DndContext>
      <div className="mx-4 h-0.5 bg-border" />
      <button
        type="button"
        className="pressable-action flex items-center justify-center gap-2 p-4 w-full text-primary font-bold text-sm cursor-pointer"
        onClick={openTelegramFriendPicker}
      >
        <svg className="w-4 h-4 stroke-[2.5]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        <span>{t("followNew")}</span>
      </button>
    </div>
  );
}

function SortableFriendRow({
  user,
  isLast,
  onOpen,
}: {
  user: FollowedUserResponse;
  isLast: boolean;
  onOpen: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: user.user_id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={isDragging ? "opacity-30" : ""}
      {...attributes}
      {...listeners}
    >
      <FriendRowBase user={user} onOpen={onOpen} />
      {!isLast && <div className="mx-4 h-px bg-border" />}
    </div>
  );
}

function FriendRowOverlay({ user }: { user: FollowedUserResponse }) {
  return (
    <div className="bg-background shadow-xl rounded-2xl scale-[1.02] cursor-grabbing ring-1 ring-border/50">
      <FriendRowBase user={user} onOpen={() => {}} />
    </div>
  );
}

function FriendRowBase({ user, onOpen }: { user: FollowedUserResponse; onOpen: () => void }) {
  return (
    <button
      type="button"
      className="discover-following-row pressable-action"
      onClick={onOpen}
    >
      <UserAvatar user={user} />
      <span>{user.first_name || user.username}</span>
    </button>
  );
}

function FulfilledWishesPanel({
  items,
}: {
  items: FulfilledWishItem[];
}) {
  const { t } = useTranslation();
  const sensors = useDiscoverDragSensors();
  const reorderMutation = useReorderFulfilledWishesMutation();
  const isReordering = useIsMutating({ mutationKey: ["reorderFulfilledWishes"] }) > 0;
  const [selectedWish, setSelectedWish] = useState<BookedWishItem | null>(null);
  const [orderIds, setOrderIds] = useState<string[]>([]);
  const [activeWish, setActiveWish] = useState<FulfilledWishItem | null>(null);
  const fulfilledItems = useMemo(() => items, [items]);

  const resolvedOrderIds = useMemo(() => {
    if (orderIds.length === 0) return fulfilledItems.map((item) => item.fulfilled_id);
    return orderIds;
  }, [orderIds, fulfilledItems]);

  const orderedItems = useMemo(() => {
    const byId = new Map(fulfilledItems.map((item) => [item.fulfilled_id, item]));
    const ordered = resolvedOrderIds
      .map((id) => byId.get(id))
      .filter((item): item is FulfilledWishItem => Boolean(item));
    const orderedIds = new Set(ordered.map((item) => item.fulfilled_id));
    return [...ordered, ...fulfilledItems.filter((item) => !orderedIds.has(item.fulfilled_id))];
  }, [fulfilledItems, resolvedOrderIds]);

  usePreventScrollWhileDragging(activeWish !== null);

  useEffect(() => {
    if (activeWish || reorderMutation.isPending || isReordering) return;
    const fulfilledIds = fulfilledItems.map((item) => item.fulfilled_id);
    setOrderIds((prev) => {
      if (prev.length === fulfilledIds.length && prev.every((id, index) => id === fulfilledIds[index])) {
        return prev;
      }
      return fulfilledIds;
    });
  }, [fulfilledItems, activeWish, reorderMutation.isPending, isReordering]);

  if (!items.length) return null;

  function handleDragStart(event: DragStartEvent) {
    const activeItem = fulfilledItems.find((item) => item.fulfilled_id === event.active.id);
    if (activeItem) setActiveWish(activeItem);
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const currentOrder = orderIds.length > 0 ? orderIds : resolvedOrderIds;
      const oldIndex = currentOrder.indexOf(active.id as string);
      const newIndex = currentOrder.indexOf(over.id as string);
      const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
      setOrderIds(newOrder);
      reorderMutation.mutate(
        { fulfilled_ids: newOrder },
        {
          onError: () => {
            setOrderIds(orderIds);
          },
        },
      );
    }
    setActiveWish(null);
  }

  return (
    <>
      <div className="panel flex flex-col p-0 overflow-hidden bg-background w-full self-start" style={{ padding: 0 }}>
        <div className="px-4 py-3">
          <h3 className="text-sm font-bold text-foreground">{t("fulfilledWishes")}</h3>
        </div>
        <div className="mx-4 h-0.5 bg-border" />
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveWish(null)}
        >
          <div className="flex flex-col">
            <SortableContext items={resolvedOrderIds} strategy={verticalListSortingStrategy}>
              {orderedItems.map((item, index) => (
                <SortableFulfilledWishRow
                  key={item.fulfilled_id}
                  item={item}
                  isLast={index === orderedItems.length - 1}
                  onOpen={() => setSelectedWish(toBookedWishItem(item))}
                />
              ))}
            </SortableContext>
          </div>
          <DragOverlay
            dropAnimation={{
              sideEffects: defaultDropAnimationSideEffects({
                styles: { active: { opacity: "0.4" } },
              }),
            }}
          >
            {activeWish ? <FulfilledWishRowOverlay item={activeWish} /> : null}
          </DragOverlay>
        </DndContext>
      </div>
      {selectedWish && (
        <BookedWishModal
          item={selectedWish}
          onClose={() => setSelectedWish(null)}
        />
      )}
    </>
  );
}

function SortableFulfilledWishRow({
  item,
  isLast,
  onOpen,
}: {
  item: FulfilledWishItem;
  isLast: boolean;
  onOpen: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.fulfilled_id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={isDragging ? "opacity-30" : ""}
      {...attributes}
      {...listeners}
    >
      <FulfilledWishRow item={item} onOpen={onOpen} />
      {!isLast && <div className="h-px bg-border/60 ml-[68px]" />}
    </div>
  );
}

function FulfilledWishRowOverlay({ item }: { item: FulfilledWishItem }) {
  return (
    <div className="bg-background shadow-xl rounded-2xl scale-[1.02] cursor-grabbing ring-1 ring-border/50">
      <FulfilledWishRow item={item} onOpen={() => {}} />
    </div>
  );
}

function FulfilledWishRow({ item, onOpen }: { item: FulfilledWishItem; onOpen: () => void }) {
  const { t } = useTranslation();
  const owner = item.owner_first_name || item.owner_username || "—";
  const fulfilledDate = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(
    new Date(item.fulfilled_at),
  );
  const amount = item.source === "group_gift" && item.user_contribution_amount
    ? ` · ${t("yourContribution")}: ${fmtAmount(item.user_contribution_amount)} ${item.wish_currency ?? ""}`.trim()
    : "";

  return (
    <button
      type="button"
      className="flex items-center gap-3 px-4 text-left w-full min-h-14"
      style={{ paddingTop: 10, paddingBottom: 10 }}
      onClick={onOpen}
    >
      <div className="relative w-12 h-12 rounded-2xl overflow-hidden shrink-0 border border-border opacity-50">
        <WishImageThumb id={item.wish_id} title={item.wish_title} imageUrl={item.images?.[0]?.thumbnail_url ?? item.images?.[0]?.medium_url} className="w-full h-full object-cover wish-image-fulfilled" />
        <div className="wish-fulfilled-check">
          <svg fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
          </svg>
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <span className="font-semibold text-sm text-foreground line-clamp-1">{item.wish_title}</span>
        <span className="text-xs text-muted block mt-0.5 line-clamp-1">
          {owner} · {item.source === "group_gift" ? `${t("groupGift")} · ` : ""}{fulfilledDate}{amount}
        </span>
      </div>
      <svg className="w-4 h-4 text-muted/60 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </button>
  );
}

function toBookedWishItem(item: FulfilledWishItem): BookedWishItem {
  return {
    reservation_id: null,
    wish_id: item.wish_id,
    wish_title: item.wish_title,
    wish_description: item.wish_description,
    wish_url: item.wish_url,
    wish_price: item.wish_price,
    wish_currency: item.wish_currency,
    wish_status: item.wish_status,
    wishlist_id: item.wishlist_id,
    wishlist_title: item.wishlist_title,
    owner_first_name: item.owner_first_name,
    owner_username: item.owner_username,
    owner_photo_url: item.owner_photo_url,
    images: item.images,
    reserved_at: item.fulfilled_at,
    is_group_gift: item.source === "group_gift",
    is_fulfilled_history: true,
    position: item.position,
    group_gift: item.source === "group_gift"
      ? {
          group_gift_id: item.group_gift_id ?? "",
          status: "archived",
          organizer_first_name: item.organizer_first_name,
          organizer_username: item.organizer_username,
          collected_amount: item.total_collected_amount ?? "0",
          total_amount: item.wish_price,
          percent_complete: 100,
          participant_count: item.contributor_count ?? 0,
          cancel_approval_count: 0,
          unbook_approval_count: 0,
          my_cancel_approval: false,
          my_unbook_approval: false,
          contributors: item.user_contribution_amount
            ? [{
                first_name: null,
                username: null,
                amount: `${fmtAmount(item.user_contribution_amount)} ${item.wish_currency ?? ""}`.trim(),
                status: "confirmed",
              }]
            : [],
        }
      : null,
  };
}

function fmtAmount(value: string) {
  const num = Number(value);
  return Number.isFinite(num) ? (Number.isInteger(num) ? String(num) : num.toFixed(2).replace(".", ",")) : value;
}

/**
 * booked wishes panel shown on discover page
 */
function BookedWishesPanel({
  items,
}: {
  items: BookedWishItem[];
}) {
  const { t } = useTranslation();
  const sensors = useDiscoverDragSensors();
  const reorderMutation = useReorderBookedWishesMutation();
  const isReordering = useIsMutating({ mutationKey: ["reorderBookedWishes"] }) > 0;
  const [selectedWish, setSelectedWish] = useState<BookedWishItem | null>(null);
  const [orderIds, setOrderIds] = useState<string[]>([]);
  const [activeWish, setActiveWish] = useState<BookedWishItem | null>(null);
  const bookedItems = useMemo(() => items, [items]);

  const resolvedOrderIds = useMemo(() => {
    if (orderIds.length === 0) return bookedItems.map((item) => item.wish_id);
    return orderIds;
  }, [orderIds, bookedItems]);

  const orderedItems = useMemo(() => {
    const byId = new Map(bookedItems.map((item) => [item.wish_id, item]));
    const ordered = resolvedOrderIds
      .map((id) => byId.get(id))
      .filter((item): item is BookedWishItem => Boolean(item));
    const orderedIds = new Set(ordered.map((item) => item.wish_id));
    return [...ordered, ...bookedItems.filter((item) => !orderedIds.has(item.wish_id))];
  }, [bookedItems, resolvedOrderIds]);

  usePreventScrollWhileDragging(activeWish !== null);

  useEffect(() => {
    if (activeWish || reorderMutation.isPending || isReordering) return;
    const wishIds = bookedItems.map((item) => item.wish_id);
    setOrderIds((prev) => {
      if (prev.length === wishIds.length && prev.every((id, index) => id === wishIds[index])) {
        return prev;
      }
      return wishIds;
    });
  }, [bookedItems, activeWish, reorderMutation.isPending, isReordering]);

  if (!items.length) return null;

  function handleDragStart(event: DragStartEvent) {
    const activeItem = bookedItems.find((item) => item.wish_id === event.active.id);
    if (activeItem) setActiveWish(activeItem);
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const currentOrder = orderIds.length > 0 ? orderIds : resolvedOrderIds;
      const oldIndex = currentOrder.indexOf(active.id as string);
      const newIndex = currentOrder.indexOf(over.id as string);
      const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
      setOrderIds(newOrder);
      reorderMutation.mutate(
        { wish_ids: newOrder },
        {
          onError: () => {
            setOrderIds(orderIds);
          },
        },
      );
    }
    setActiveWish(null);
  }

  return (
    <>
      <div className="panel flex flex-col p-0 overflow-hidden bg-background w-full self-start" style={{ padding: 0 }}>
        <div className="px-4 py-3">
          <h3 className="text-sm font-bold text-foreground">{t("bookedWishes")}</h3>
        </div>
        <div className="mx-4 h-0.5 bg-border" />
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveWish(null)}
        >
          <div className="flex flex-col">
            <SortableContext items={resolvedOrderIds} strategy={verticalListSortingStrategy}>
              {orderedItems.map((item, index) => (
                <SortableBookedWishRow
                  key={item.wish_id}
                  item={item}
                  isLast={index === orderedItems.length - 1}
                  onOpen={() => setSelectedWish(item)}
                />
              ))}
            </SortableContext>
          </div>
          <DragOverlay
            dropAnimation={{
              sideEffects: defaultDropAnimationSideEffects({
                styles: { active: { opacity: "0.4" } },
              }),
            }}
          >
            {activeWish ? <BookedWishRowOverlay item={activeWish} /> : null}
          </DragOverlay>
        </DndContext>
      </div>
      {selectedWish && (
        <BookedWishModal
          item={selectedWish}
          onClose={() => setSelectedWish(null)}
        />
      )}
    </>
  );
}

function SortableBookedWishRow({
  item,
  isLast,
  onOpen,
}: {
  item: BookedWishItem;
  isLast: boolean;
  onOpen: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.wish_id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={isDragging ? "opacity-30" : ""}
      {...attributes}
      {...listeners}
    >
      <BookedWishRow item={item} onOpen={onOpen} />
      {!isLast && <div className="h-px bg-border/60 ml-[68px]" />}
    </div>
  );
}

function BookedWishRowOverlay({ item }: { item: BookedWishItem }) {
  return (
    <div className="bg-background shadow-xl rounded-2xl scale-[1.02] cursor-grabbing ring-1 ring-border/50">
      <BookedWishRow item={item} onOpen={() => {}} />
    </div>
  );
}

type BookedWishRowProps = {
  item: BookedWishItem;
  onOpen: () => void;
};

/**
 * single booked wish row
 */
function BookedWishRow({ item, onOpen }: BookedWishRowProps) {
  const isDeleted = item.wish_status === "completed";

  return (
    <button
      type="button"
      className={`flex items-center gap-3 px-4 text-left w-full min-h-14 ${isDeleted ? "opacity-50" : ""}`}
      style={{ paddingTop: 10, paddingBottom: 10 }}
      onClick={onOpen}
    >
      <div className="w-10 h-10 rounded-xl overflow-hidden shrink-0 border border-border">
        <WishImageThumb id={item.wish_id} title={item.wish_title} imageUrl={item.images?.[0]?.thumbnail_url ?? item.images?.[0]?.medium_url} className="w-full h-full object-cover" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-semibold text-sm text-foreground line-clamp-1">{item.wish_title}</span>
        </div>
        <span className="text-xs text-muted block mt-0.5 line-clamp-1">
          {item.owner_first_name || item.owner_username || "—"} · {item.wishlist_title}
        </span>
      </div>
      <svg className="w-4 h-4 text-muted/60 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </button>
  );
}

type BookedWishModalProps = {
  item: BookedWishItem;
  onClose: () => void;
};


/**
 * booked wish details
 */
function BookedWishModal({ item, onClose }: BookedWishModalProps) {
  const { t } = useTranslation();
  const [active, setActive] = useState(false);
  const [view, setView] = useState<"wish" | "viewGroupGift">("wish");
  const [previousView, setPreviousView] = useState<"wish" | "viewGroupGift" | null>(null);
  const [navDirection, setNavDirection] = useState<"forward" | "back">("forward");
  const [groupGiftActionMode, setGroupGiftActionMode] = useState<ActionMode>("overview");
  const [groupGiftFocusMode, setGroupGiftFocusMode] = useState(false);
  const cancelMutation = useCancelReservationMutation(item.wishlist_id);
  const liveGroupGift = useGroupGiftQuery(item.wish_id);

  useEffect(() => {
    requestAnimationFrame(() => setActive(true));
  }, []);

  function handleClose() {
    setActive(false);
    window.setTimeout(onClose, 340);
  }

  function openGroupGift() {
    setGroupGiftActionMode("overview");
    setNavDirection("forward");
    setPreviousView(view);
    setView("viewGroupGift");
  }

  function closeGroupGift() {
    setNavDirection("back");
    setPreviousView(view);
    setView("wish");
  }

  function fmtPrice(price: string) {
    const num = parseFloat(price);
    return isNaN(num) ? price.replace(".", ",") : (Number.isInteger(num) ? String(num) : num.toFixed(2).replace(".", ","));
  }
  const unbookLabel = item.wish_price
    ? `${t("unbookWish")} · ${fmtPrice(item.wish_price)} ${item.wish_currency ?? ""}`.trim()
    : t("unbookWish");

  const groupGiftTitle = groupGiftActionMode === "contribute"
    ? t("makeContribution")
    : groupGiftActionMode === "editPayment"
    ? t("editPaymentDetails")
    : groupGiftActionMode === "removeContribution"
    ? t("removeContribution")
    : (groupGiftActionMode === "cancel" || groupGiftActionMode === "purchase" || groupGiftActionMode === "unbook" || groupGiftActionMode === "leave")
    ? ""
    : t("groupGift");

  function renderWishView() {
    const archivedGroupGift = item.group_gift?.status === "archived" ? item.group_gift : null;
    const ownerWishlistLine = `${item.owner_first_name || item.owner_username || "—"} · ${item.wishlist_title}`;
    return (
      <div className="public-nav-content">
        <section className="flex flex-col items-center gap-3">
          <div className="public-wish-gallery relative">
            <WishImageThumb
              id={item.wish_id}
              title={item.wish_title}
              imageUrl={item.images?.[0]?.medium_url ?? item.images?.[0]?.thumbnail_url}
              className={`w-full h-full object-cover ${item.is_fulfilled_history ? "wish-image-fulfilled" : ""}`}
            />
            {item.is_fulfilled_history ? (
              <span className="wish-fulfilled-badge">{t("wishFulfilled")}</span>
            ) : null}
          </div>
          <p className="text-xs text-muted text-center">
            {ownerWishlistLine}
          </p>
          {item.wish_url ? (
            <a
              href={item.wish_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-muted hover:text-foreground transition-colors mt-0.5"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              {t("openProductPage") ?? "Open wish's page"}
            </a>
          ) : null}
          {item.images.length > 1 ? (
            <div className="grid grid-cols-4 gap-2 w-full">
              {item.images.slice(0, 4).map((image) => (
                <div key={image.id} className="aspect-square rounded-xl overflow-hidden border border-border">
                  <WishImageThumb
                    id={item.wish_id}
                    title={item.wish_title}
                    imageUrl={image.thumbnail_url ?? image.medium_url}
                    className="w-full h-full object-cover"
                  />
                </div>
              ))}
            </div>
          ) : null}
        </section>

        {item.is_fulfilled_history && item.wish_price ? (
          <p className="text-xl font-extrabold text-primary text-center">
            {fmtPrice(item.wish_price)} {item.wish_currency ?? ""}
          </p>
        ) : null}

        {item.wish_description ? (
          <section className={item.is_fulfilled_history ? "px-4 mt-2" : "mt-3"}>
            {item.is_fulfilled_history ? (
              <div className="rounded-xl border border-border bg-muted/5 px-3 py-2.5 text-left">
                <h4 className="text-[10px] font-extrabold uppercase tracking-wider text-muted mb-1.5">
                  {t("descriptionLabel")}
                </h4>
                <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/60">
                  {item.wish_description}
                </p>
              </div>
            ) : (
              <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/80 text-center">
                {item.wish_description}
              </p>
            )}
          </section>
        ) : null}

        <section className="flex flex-col gap-2 w-full mt-3">
          {item.is_group_gift ? (
            <>
              {(archivedGroupGift ?? liveGroupGift.data ?? item.group_gift) ? (() => {
                const gg = archivedGroupGift ?? liveGroupGift.data ?? item.group_gift!;
                return (
                  <button
                    type="button"
                    className="w-full text-left rounded-xl border border-border bg-muted/5 px-3 py-2.5 flex flex-col gap-1.5"
                    onClick={openGroupGift}
                  >
                    <div className="flex justify-between items-center text-xs text-muted">
                      <span>{t("groupGift")}</span>
                      <span>
                        {gg.status === "archived"
                          ? t("wishFulfilled")
                          : gg.status === "cancelled"
                          ? t("giftCancelled")
                          : gg.status === "completed" || gg.percent_complete >= 100
                          ? t("giftComplete")
                          : t("giftProgress").replace("{percent}", String(gg.percent_complete))}
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-muted/20 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary transition-[width] duration-700 ease-out"
                        style={{ width: `${Math.min(100, gg.percent_complete)}%` }}
                      />
                    </div>
                  </button>
                );
              })() : null}
            </>
          ) : item.is_fulfilled_history ? null : (
            <button
              type="button"
              className="theme-confirm-danger w-full h-12 rounded-xl text-sm font-bold"
              disabled={cancelMutation.isPending}
              onClick={() =>
                cancelMutation.mutate(
                  { reservationId: item.reservation_id ?? "", wishId: item.wish_id },
                  { onSuccess: handleClose },
                )
              }
            >
              {cancelMutation.isPending ? t("cancellingReservation") : unbookLabel}
            </button>
          )}
        </section>
      </div>
    );
  }

  function renderGroupGiftView() {
    if (item.group_gift?.status === "archived") {
      const gg = item.group_gift;
      const organizer = gg.organizer_first_name || gg.organizer_username || "—";
      return (
        <div className="public-nav-content px-1 pb-1">
          <section className="flex flex-col gap-3 rounded-xl border border-border bg-muted/5 px-3 py-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-bold text-foreground">{t("groupGift")}</span>
              <span className="text-xs font-bold text-green-600">{t("wishFulfilled")}</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <p className="text-muted">{t("groupGiftOrganizer")}</p>
                <p className="font-semibold text-foreground truncate">{organizer}</p>
              </div>
              <div>
                <p className="text-muted">{t("contributors")}</p>
                <p className="font-semibold text-foreground">{gg.participant_count}</p>
              </div>
              <div>
                <p className="text-muted">{t("yourContribution")}</p>
                <p className="font-semibold text-foreground">
                  {gg.contributors[0]?.amount ?? "—"}
                </p>
              </div>
              <div>
                <p className="text-muted">{t("groupGiftTotalCollected")}</p>
                <p className="font-semibold text-foreground">
                  {fmtAmount(gg.collected_amount)} {item.wish_currency ?? ""}
                </p>
              </div>
            </div>
          </section>
        </div>
      );
    }
    return (
      <div className="public-nav-content px-1 pb-1">
        <ViewGroupGiftContent
          wishId={item.wish_id}
          showTitle={false}
          actionMode={groupGiftActionMode}
          onClose={closeGroupGift}
          onActionModeChange={setGroupGiftActionMode}
          onFocusModeChange={setGroupGiftFocusMode}
        />
      </div>
    );
  }

  function renderView(v: "wish" | "viewGroupGift") {
    return v === "viewGroupGift" ? renderGroupGiftView() : renderWishView();
  }

  const modalTitle = view === "viewGroupGift" ? groupGiftTitle : item.wish_title;

  return (
    <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={handleClose}>
      <div
        className={`modal-sheet modal-sheet-nav-host ${active ? "visible" : ""} ${groupGiftFocusMode ? "keyboard-focus-mode" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-handle" />
        <div className={`flex items-center justify-between mb-4 ${groupGiftFocusMode ? "modal-focus-collapsed" : "modal-focus-section"}`}>
          {view === "viewGroupGift" && groupGiftActionMode === "overview" ? (
            <button
              type="button"
              className="pressable-link w-10 h-10 inline-flex items-center justify-center rounded-xl text-muted"
              onClick={closeGroupGift}
              aria-label={t("back")}
            >
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          ) : (
            <span className="w-10" />
          )}
          <h3 className="modal-title font-bold text-lg text-center text-foreground line-clamp-2 flex items-center gap-2">
            {modalTitle}
          </h3>
          <span className="w-10" />
        </div>

        <div className="public-nav-viewport">
          {previousView ? (
            <div className={`public-nav-frame public-nav-exit-${navDirection}`} key={`prev-${previousView}`}>
              {renderView(previousView)}
            </div>
          ) : null}
          <div
            className={`public-nav-frame ${previousView ? `public-nav-enter-${navDirection}` : ""}`}
            key={`curr-${view}`}
            onAnimationEnd={() => setPreviousView(null)}
          >
            {renderView(view)}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * open bot contact picker
 */
function openTelegramFriendPicker() {
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME?.trim().replace(/^@/, "");
  if (!botUsername) return;

  const botUrl = `https://t.me/${botUsername}`;
  const webApp = (window as TelegramWindow).Telegram?.WebApp;

  try {
    (webApp as { HapticFeedback?: { impactOccurred?: (style: string) => void } })?.HapticFeedback?.impactOccurred?.("medium");
  } catch {}

  if (webApp?.openTelegramLink) {
    webApp.openTelegramLink(botUrl);
    window.setTimeout(() => webApp.close?.(), 450);
    return;
  }

  window.location.assign(botUrl);
}
