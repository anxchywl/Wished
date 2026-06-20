"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { PublicWishlistNavigator } from "@/features/users/public-wishlist-navigator";
import { UserAvatar } from "@/features/users/user-avatar";
import { useFollowingQuery } from "@/features/users/hooks";
import { useBookedWishesQuery, useCancelReservationMutation } from "@/features/reservations/hooks";
import { useProfileQuery, useUpdatePrivacyMutation } from "@/features/profile/hooks";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { logStartup } from "@/lib/debug/startup-log";
import { isAuthFailure, isAuthPending, useAuthStore } from "@/stores/auth-store";
import { useRouter, useSearchParams } from "next/navigation";
import type { BookedWishItem } from "@/features/reservations/api";
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

  function handleChange(value: BookingVisibility) {
    updatePrivacy.mutate(
      { booking_visibility: value },
      {
        onSuccess: () => {
          setActive(false);
          window.setTimeout(() => setOpen(false), 340);
        },
      },
    );
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
            <h3 className="modal-title font-bold text-base mb-4 text-center">{t("bookingVisibilityTitle")}</h3>
            <div className="flex flex-col gap-2">
              {(["hide", "anonymous", "names"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`flex flex-col items-start px-4 py-3 rounded-xl border transition-all text-left ${
                    currentVisibility === option
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border bg-background text-foreground"
                  }`}
                  onClick={() => handleChange(option)}
                  disabled={updatePrivacy.isPending}
                >
                  <span className="text-sm font-bold">
                    {option === "hide"
                      ? t("bookingVisibilityHide")
                      : option === "anonymous"
                      ? t("bookingVisibilityAnonymous")
                      : t("bookingVisibilityNames")}
                  </span>
                  <span className="text-xs text-muted mt-0.5">
                    {option === "hide"
                      ? t("bookingVisibilityHideDesc")
                      : option === "anonymous"
                      ? t("bookingVisibilityAnonymousDesc")
                      : t("bookingVisibilityNamesDesc")}
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
  const profileToken = searchParams.get("profile_token");
  const selectedWishlistId = searchParams.get("wishlist");
  const selectedWishId = searchParams.get("wish");
  const followingQuery = useFollowingQuery();
  const followedUsers = followingQuery.data?.items ?? [];
  const bookedWishesQuery = useBookedWishesQuery();
  const bookedWishes = bookedWishesQuery.data?.items ?? [];
  const { t } = useTranslation();

  const guardDecision = isAuthPending(authStatus)
    ? "startup"
    : isAuthFailure(authStatus) || !accessToken
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
        ) : followingQuery.isLoading ? (
          <div className="panel flex flex-col gap-3 p-4 w-full">
            <div className="public-skeleton h-16 w-full rounded-xl" />
            <div className="public-skeleton h-16 w-full rounded-xl" />
            <div className="public-skeleton h-16 w-full rounded-xl" />
          </div>
        ) : followedUsers.length > 0 ? (
          <>
          <div className="panel discover-following-panel flex flex-col p-0 overflow-hidden bg-background w-full self-start">
            <div className="px-4 py-3 border-b border-border">
              <h3 className="text-sm font-bold text-foreground">{t("friends")}</h3>
            </div>
            <div className="discover-following">
              {followedUsers.map((user) => (
                <button
                  key={user.username}
                  type="button"
                  className="discover-following-row pressable-action"
                  onClick={() => {
                    if (user.username) router.replace(`/users?profile=${encodeURIComponent(user.username)}`);
                  }}
                  disabled={!user.username}
                >
                  <UserAvatar user={user} />
                  <span>{user.first_name || user.username}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              className="pressable-action flex items-center justify-center gap-2 py-3 px-4 w-full text-primary font-semibold text-sm cursor-pointer border-t border-border"
              onClick={openTelegramFriendPicker}
            >
              <svg className="w-4 h-4 stroke-[2.5]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              <span>{t("followNew")}</span>
            </button>
          </div>
          <BookedWishesPanel items={bookedWishes} isLoading={bookedWishesQuery.isLoading} />
          </>
        ) : (
          <>
          <BookedWishesPanel items={bookedWishes} isLoading={bookedWishesQuery.isLoading} />
          <section className={`discover-launch ${bookedWishes.length ? "discover-launch-after-bookings" : ""}`}>
            <h2>{t("findTelegramFriends")}</h2>
            <button type="button" className="discover-launch-button" onClick={openTelegramFriendPicker}>
              <span>{t("chooseTelegramUsers")}</span>
            </button>
          </section>
          </>
        )}

      </main>

      <PublicWishlistNavigator
        open={Boolean(selectedUsername)}
        username={selectedUsername}
        profileToken={profileToken}
        initialWishlistId={selectedWishlistId}
        initialWishId={selectedWishId}
        onClose={() => router.replace("/users")}
      />

    </>
  );
}

/**
 * booked wishes panel shown on discover page
 */
function BookedWishesPanel({
  items,
  isLoading,
}: {
  items: BookedWishItem[];
  isLoading: boolean;
}) {
  const { t } = useTranslation();
  const [selectedWish, setSelectedWish] = useState<BookedWishItem | null>(null);

  if (isLoading) {
    return (
      <div className="panel flex flex-col gap-3 p-4 w-full">
        <div className="public-skeleton h-12 w-full rounded-xl" />
      </div>
    );
  }

  if (!items.length) return null;

  return (
    <>
      <div className="panel flex flex-col p-0 overflow-hidden bg-background w-full self-start">
        <div className="px-4 py-3 border-b border-border">
          <h3 className="text-sm font-bold text-foreground">{t("bookedWishes")}</h3>
        </div>
        <div className="flex flex-col divide-y divide-border">
          {items.map((item) => (
            <BookedWishRow
              key={item.reservation_id}
              item={item}
              onOpen={() => setSelectedWish(item)}
            />
          ))}
        </div>
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
      className={`flex items-center gap-3 px-4 py-3 text-left w-full ${isDeleted ? "opacity-50" : ""}`}
      onClick={onOpen}
    >
      <div className="w-10 h-10 rounded-xl overflow-hidden shrink-0 border border-border">
        <WishImageThumb id={item.wish_id} title={item.wish_title} imageUrl={item.images?.[0]?.url} className="w-full h-full object-cover" />
      </div>
      <div className="flex-1 min-w-0">
        <span className="font-semibold text-sm text-foreground line-clamp-1">{item.wish_title}</span>
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
  const cancelMutation = useCancelReservationMutation(item.wishlist_id);

  useEffect(() => {
    requestAnimationFrame(() => setActive(true));
  }, []);

  function handleClose() {
    setActive(false);
    window.setTimeout(onClose, 340);
  }

  return (
    <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={handleClose}>
      <div className={`modal-sheet ${active ? "visible" : ""}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-handle" />
        <h3 className="modal-title font-bold text-lg mb-4 text-center">{item.wish_title}</h3>
          <div className="flex flex-col items-center gap-4">
            <div className="w-full max-w-[210px] aspect-square rounded-3xl overflow-hidden border border-border shadow-lg">
              <WishImageThumb
                id={item.wish_id}
                title={item.wish_title}
                imageUrl={item.images?.[0]?.medium_url ?? item.images?.[0]?.url}
                className="w-full h-full object-cover"
              />
            </div>
            {item.images.length > 1 ? (
              <div className="grid grid-cols-4 gap-2 w-full">
                {item.images.slice(0, 4).map((image) => (
                  <div key={image.id} className="aspect-square rounded-xl overflow-hidden border border-border">
                    <WishImageThumb
                      id={item.wish_id}
                      title={item.wish_title}
                      imageUrl={image.thumbnail_url ?? image.url}
                      className="w-full h-full object-cover"
                    />
                  </div>
                ))}
              </div>
            ) : null}
            {item.wish_price ? (
              <p className="text-lg font-extrabold text-primary">
                {item.wish_price.replace(".", ",")} {item.wish_currency ?? ""}
              </p>
            ) : null}
            <p className="text-xs text-muted text-center">
              {item.owner_first_name || item.owner_username || "—"} · {item.wishlist_title}
            </p>
            <div className="w-full flex flex-col gap-2">
              <button
                type="button"
                className="theme-confirm-danger w-full h-12 rounded-xl text-sm font-bold"
                disabled={cancelMutation.isPending}
                onClick={() =>
                  cancelMutation.mutate(
                    { reservationId: item.reservation_id, wishId: item.wish_id },
                    { onSuccess: handleClose },
                  )
                }
              >
                {cancelMutation.isPending ? t("cancellingReservation") : t("unbookWish")}
              </button>
            </div>
            {item.wish_description ? (
              <div className="w-full rounded-2xl border border-border bg-muted/10 px-4 py-3">
                <p className="text-[10px] font-extrabold uppercase tracking-wider text-muted">{t("descriptionLabel")}</p>
                <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
                  {item.wish_description}
                </p>
              </div>
            ) : null}
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
