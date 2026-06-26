"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { PublicWishlistNavigator } from "@/features/users/public-wishlist-navigator";
import { UserAvatar } from "@/features/users/user-avatar";
import { useFollowingQuery } from "@/features/users/hooks";
import { useBookedWishesQuery, useCancelReservationMutation } from "@/features/reservations/hooks";
import { useToggleGroupGiftApprovalMutation } from "@/features/group-gifts/hooks";
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
  const currentGroupGiftVisibility =
    (profileQuery.data?.privacy?.group_gift_visibility as BookingVisibility | undefined) ?? "hide";

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

  function handleGroupGiftChange(value: BookingVisibility) {
    updatePrivacy.mutate(
      { group_gift_visibility: value },
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
            <h3 className="modal-title font-bold text-base mt-5 mb-4 text-center">{t("groupGiftVisibilityTitle")}</h3>
            <div className="flex flex-col gap-2">
              {(["hide", "anonymous", "names"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`flex flex-col items-start px-4 py-3 rounded-xl border transition-all text-left ${
                    currentGroupGiftVisibility === option
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border bg-background text-foreground"
                  }`}
                  onClick={() => handleGroupGiftChange(option)}
                  disabled={updatePrivacy.isPending}
                >
                  <span className="text-sm font-bold">
                    {option === "hide"
                      ? t("groupGiftVisibilityHide")
                      : option === "anonymous"
                      ? t("groupGiftVisibilityAnonymous")
                      : t("groupGiftVisibilityNames")}
                  </span>
                  <span className="text-xs text-muted mt-0.5">
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
  const selectedUserId = searchParams.get("profile_id");
  const profileToken = searchParams.get("profile_token");
  const selectedWishlistId = searchParams.get("wishlist");
  const selectedWishId = searchParams.get("wish");
  const shareToken = searchParams.get("share_token");
  const followingQuery = useFollowingQuery();
  const followedUsers = followingQuery.data?.items ?? [];
  const bookedWishesQuery = useBookedWishesQuery();
  const bookedWishes = bookedWishesQuery.data?.items ?? [];
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
        ) : followedUsers.length > 0 ? (
          <>
          <div className="panel discover-following-panel flex flex-col p-0 overflow-hidden bg-background w-full self-start" style={{ padding: 0 }}>
            <div className="px-4 py-3 border-b-2 border-border">
              <h3 className="text-sm font-bold text-foreground">{t("friends")}</h3>
            </div>
            <div className="discover-following">
              {followedUsers.map((user, index) => (
                <div key={user.user_id}>
                  <button
                    type="button"
                    className="discover-following-row pressable-action"
                    onClick={() => {
                      router.replace(`/users?profile_id=${encodeURIComponent(user.user_id)}`);
                    }}
                  >
                    <UserAvatar user={user} />
                    <span>{user.first_name || user.username}</span>
                  </button>
                  {index < followedUsers.length - 1 && <div className="h-px bg-border" />}
                </div>
              ))}
            </div>
            <div className="h-0.5 bg-border" />
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
          <BookedWishesPanel items={bookedWishes} />
          </>
        ) : (
          <>
          <BookedWishesPanel items={bookedWishes} />
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
        open={Boolean(selectedUsername || selectedUserId)}
        username={selectedUsername}
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

/**
 * booked wishes panel shown on discover page
 */
function BookedWishesPanel({
  items,
}: {
  items: BookedWishItem[];
}) {
  const { t } = useTranslation();
  const [selectedWish, setSelectedWish] = useState<BookedWishItem | null>(null);

  if (!items.length) return null;

  return (
    <>
      <div className="panel flex flex-col p-0 overflow-hidden bg-background w-full self-start" style={{ padding: 0 }}>
        <div className="px-4 py-3 border-b-2 border-border">
          <h3 className="text-sm font-bold text-foreground">{t("bookedWishes")}</h3>
        </div>
        <div className="flex flex-col">
          {items.map((item, index) => (
            <div key={item.reservation_id}>
              <BookedWishRow item={item} onOpen={() => setSelectedWish(item)} />
              {index < items.length - 1 && <div className="h-px bg-border/60 ml-[68px]" />}
            </div>
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
  const { t } = useTranslation();
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
          {item.is_group_gift ? (
            <span className="shrink-0 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-primary/10 text-primary">
              {t("groupGiftBadge")}
            </span>
          ) : null}
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

function formatGiftAmount(amount: string | null | undefined): string {
  if (!amount) return "";
  const num = Number(amount);
  if (!Number.isFinite(num)) return amount;
  return new Intl.NumberFormat("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(num);
}

/**
 * booked wish details
 */
function BookedWishModal({ item, onClose }: BookedWishModalProps) {
  const { t } = useTranslation();
  const [active, setActive] = useState(false);
  const cancelMutation = useCancelReservationMutation(item.wishlist_id);
  const approvalMutation = useToggleGroupGiftApprovalMutation(item.wish_id, item.group_gift?.group_gift_id ?? "");

  useEffect(() => {
    requestAnimationFrame(() => setActive(true));
  }, []);

  function handleClose() {
    setActive(false);
    window.setTimeout(onClose, 340);
  }

  function fmtPrice(price: string) {
    const num = parseFloat(price);
    return isNaN(num) ? price.replace(".", ",") : (Number.isInteger(num) ? String(num) : num.toFixed(2).replace(".", ","));
  }
  const unbookLabel = item.wish_price
    ? `${t("unbookWish")} · ${fmtPrice(item.wish_price)} ${item.wish_currency ?? ""}`.trim()
    : t("unbookWish");

  const gg = item.group_gift;
  const organizerName = gg
    ? (gg.organizer_first_name || (gg.organizer_username ? `@${gg.organizer_username}` : null))
    : null;

  return (
    <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={handleClose}>
      <div className={`modal-sheet ${active ? "visible" : ""}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-handle" />
        <div className="flex items-center justify-center gap-2 mb-3">
          <h3 className="modal-title font-bold text-lg text-center">{item.wish_title}</h3>
          {item.is_group_gift ? (
            <span className="shrink-0 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-primary/10 text-primary">
              {t("groupGiftBadge")}
            </span>
          ) : null}
        </div>

        <section className="flex flex-col items-center gap-3">
          <div className="public-wish-gallery relative">
            <WishImageThumb
              id={item.wish_id}
              title={item.wish_title}
              imageUrl={item.images?.[0]?.medium_url ?? item.images?.[0]?.thumbnail_url}
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
                    imageUrl={image.thumbnail_url ?? image.medium_url}
                    className="w-full h-full object-cover"
                  />
                </div>
              ))}
            </div>
          ) : null}
        </section>

        {item.wish_description ? (
          <section className="px-4 mt-3">
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/80 text-center">
              {item.wish_description}
            </p>
          </section>
        ) : null}

        <section className="flex flex-col gap-2 w-full mt-3 px-4">
          <p className="text-xs text-muted text-center mb-1">
            {item.owner_first_name || item.owner_username || "—"} · {item.wishlist_title}
          </p>

          {item.is_group_gift && gg ? (
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5 bg-muted/5 rounded-xl p-3 border border-border text-sm">
                {organizerName ? (
                  <div className="flex justify-between items-center gap-2">
                    <span className="text-xs text-muted">{t("groupGiftOrganizer")}</span>
                    <span className="font-semibold text-foreground">{organizerName}</span>
                  </div>
                ) : null}
                <div className="flex justify-between items-center gap-2">
                  <span className="text-xs text-muted">{t("groupGiftTotalCollected")}</span>
                  <span className="font-semibold text-foreground">
                    {formatGiftAmount(gg.collected_amount)}
                    {gg.total_amount ? ` / ${formatGiftAmount(gg.total_amount)}` : ""}
                  </span>
                </div>
                <div className="flex justify-between items-center gap-2">
                  <span className="text-xs text-muted">{t("contributors")}</span>
                  <span className="font-semibold text-foreground">{gg.participant_count}</span>
                </div>
                {gg.contributors.length > 0 ? (
                  <div className="flex flex-col gap-1 mt-1 pt-2 border-t border-border">
                    {gg.contributors.map((c, i) => {
                      const name = c.first_name || (c.username ? `@${c.username}` : t("unknownUser") ?? "—");
                      return (
                        <div key={i} className="flex justify-between items-center gap-2">
                          <span className="text-xs text-foreground truncate">{name}</span>
                          {c.amount ? (
                            <span className="text-xs font-semibold text-foreground shrink-0">{formatGiftAmount(c.amount)}</span>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                ) : null}
              </div>

              {gg.status === "completed" ? (
                <div className="flex flex-col gap-2">
                  <p className="text-xs text-muted text-center">{t("groupGiftUnbookInfo")}</p>
                  {gg.participant_count > 1 ? (
                    <p className="text-xs font-semibold text-center text-foreground">
                      {t("approvedOf")
                        .replace("{approved}", String(gg.unbook_approval_count))
                        .replace("{total}", String(gg.participant_count))}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    className={`w-full h-12 rounded-xl text-sm font-bold disabled:opacity-60 transition-colors ${
                      gg.my_unbook_approval ? "bg-primary text-white" : "theme-confirm-danger"
                    }`}
                    disabled={approvalMutation.isPending}
                    onClick={() =>
                      approvalMutation.mutate("unbook", {
                        onSuccess: (result) => { if (result === null) handleClose(); },
                      })
                    }
                  >
                    {approvalMutation.isPending
                      ? t("saving")
                      : gg.my_unbook_approval
                      ? t("cancelButton")
                      : t("unbookApproval")}
                  </button>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  <p className="text-xs text-muted text-center">{t("groupGiftCancelInfo")}</p>
                  {gg.participant_count > 1 ? (
                    <p className="text-xs font-semibold text-center text-foreground">
                      {t("approvedOf")
                        .replace("{approved}", String(gg.cancel_approval_count))
                        .replace("{total}", String(gg.participant_count))}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    className={`w-full h-12 rounded-xl text-sm font-bold disabled:opacity-60 transition-colors ${
                      gg.my_cancel_approval ? "bg-primary text-white" : "theme-confirm-danger"
                    }`}
                    disabled={approvalMutation.isPending}
                    onClick={() =>
                      approvalMutation.mutate("cancel", {
                        onSuccess: (result) => { if (result === null) handleClose(); },
                      })
                    }
                  >
                    {approvalMutation.isPending
                      ? t("saving")
                      : gg.my_cancel_approval
                      ? t("cancelButton")
                      : t("cancelApproval")}
                  </button>
                </div>
              )}
            </div>
          ) : (
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

          {item.wish_url ? (
            <a
              href={item.wish_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-1.5 h-9 w-full rounded-xl text-xs font-semibold text-muted hover:text-foreground transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              {t("openProductPage") ?? "Open wish's page"}
            </a>
          ) : null}
        </section>
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
