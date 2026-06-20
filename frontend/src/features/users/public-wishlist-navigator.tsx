// public wishlist navigator
"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { useReservationStatusQuery, useCreateReservationMutation } from "@/features/reservations/hooks";
import { UserAvatar } from "@/features/users/user-avatar";
import { getUserProfile, type UserProfileResponse } from "@/features/users/api";
import { userQueryKeys, useFollowMutation, useUserProfileQuery } from "@/features/users/hooks";
import { getWishlist, listUserWishlists } from "@/features/wishlists/api";
import { wishlistQueryKeys } from "@/features/wishlists/query-keys";
import type { Wishlist } from "@/features/wishlists/types";
import { parseWishlistDescription } from "@/features/wishlists/utils";
import { getWishlistCoverStyle, WishImageThumb } from "@/features/wishlists/wishlist-visuals";
import { listWishes } from "@/features/wishes/api";
import { useCopyWishMutation, useWishesQuery } from "@/features/wishes/hooks";
import { wishQueryKeys } from "@/features/wishes/query-keys";
import type { Wish } from "@/features/wishes/types";
import { useWishlistsQuery, useUserWishlistsQuery, useWishlistQuery } from "@/features/wishlists/hooks";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { logStartup } from "@/lib/debug/startup-log";
import { isAuthFailure, isAuthPending, useAuthStore } from "@/stores/auth-store";

type PublicWishlistNavigatorProps = {
  open: boolean;
  username: string | null;
  profileToken?: string | null;
  initialUser?: UserProfileResponse | null;
  initialWishlistId?: string | null;
  initialWishId?: string | null;
  onClose: () => void;
};

type NavigationView = "user" | "wishlist" | "wish" | "copy";
type NavigationFrame = {
  view: NavigationView;
  wishlistId?: string;
  wishlistTitle?: string;
  wishId?: string;
  wishTitle?: string;
};

type NavigationDirection = "forward" | "back";

/**
 * navigate public wishlists
 */
export function PublicWishlistNavigator({
  open,
  username,
  profileToken,
  initialUser,
  initialWishlistId,
  initialWishId,
  onClose,
}: PublicWishlistNavigatorProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const [active, setActive] = useState(false);
  const [stack, setStack] = useState<NavigationFrame[]>([{ view: "user" }]);
  const [direction, setDirection] = useState<NavigationDirection>("forward");
  const [previousFrame, setPreviousFrame] = useState<NavigationFrame | null>(null);
  const current = stack[stack.length - 1];
  const { t } = useTranslation();

  useEffect(() => {
    setActive(open);
    if (open) {
      setStack(
        initialWishlistId && initialWishId
          ? [
              { view: "user" },
              { view: "wishlist", wishlistId: initialWishlistId },
              { view: "wish", wishlistId: initialWishlistId, wishId: initialWishId },
            ]
          : initialWishlistId
            ? [
                { view: "user" },
                { view: "wishlist", wishlistId: initialWishlistId },
              ]
          : [{ view: "user" }],
      );
      setDirection("forward");
      setPreviousFrame(null);
    }
  }, [initialWishlistId, initialWishId, open, username]);

  if (!open || !username) return null;

  const activeUsername = username.trim().replace(/^@/, "");
  const guardDecision = isAuthPending(authStatus)
    ? "startup"
    : isAuthFailure(authStatus) || (authStatus !== "authenticated" && !accessToken)
      ? "auth_required"
      : "app";

  logStartup("route guard decision", authStatus, {
    component: "PublicWishlistNavigator",
    decision: guardDecision,
    hasAccessToken: Boolean(accessToken),
  });

  function handleClose() {
    setActive(false);
    window.setTimeout(onClose, 340);
  }

  function handleBack() {
    if (stack.length === 1) {
      handleClose();
      return;
    }
    setDirection("back");
    setPreviousFrame(current);
    setStack((currentStack) => currentStack.slice(0, -1));
  }

  function handleWishlistOpen(wishlistId: string, wishlistTitle?: string) {
    setDirection("forward");
    setPreviousFrame(current);
    setStack((currentStack) => [...currentStack, { view: "wishlist", wishlistId, wishlistTitle }]);
  }

  function handleCopyOpen(wishlistId: string, wishId: string) {
    setDirection("forward");
    setPreviousFrame(current);
    setStack((currentStack) => [...currentStack, { view: "copy", wishlistId, wishId }]);
  }

  function handleCopySuccess() {
    handleClose();
  }

  function handleWishOpen(wishlistId: string, wishId: string, wishTitle?: string) {
    setDirection("forward");
    setPreviousFrame(current);
    setStack((currentStack) => [...currentStack, { view: "wish", wishlistId, wishId, wishTitle }]);
  }

  function renderFrame(frame: NavigationFrame) {
    if (frame.view === "user") {
      return (
        <PublicUserView
          username={activeUsername}
          profileToken={profileToken}
          initialUser={initialUser}
          onOpenWishlist={handleWishlistOpen}
          onClose={handleClose}
        />
      );
    }

    if (frame.view === "wishlist" && frame.wishlistId) {
      return <PublicWishlistView wishlistId={frame.wishlistId} onOpenWish={handleWishOpen} />;
    }

    if (frame.view === "wish" && frame.wishlistId && frame.wishId) {
      return <PublicWishView wishlistId={frame.wishlistId} wishId={frame.wishId} />;
    }

    if (frame.view === "copy" && frame.wishlistId && frame.wishId) {
      return <PublicCopyView wishlistId={frame.wishlistId} wishId={frame.wishId} onCopySuccess={handleCopySuccess} />;
    }

    return null;
  }

  return (
    <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={handleClose}>
      <div
        className={`modal-sheet public-nav-sheet ${active ? "visible" : ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-handle" />
        <div className="public-nav-header">
          {stack.length > 1 ? (
            <button
              type="button"
              className="w-10 h-10 inline-flex items-center justify-center text-foreground hover:opacity-70 transition-opacity"
              onClick={handleBack}
              aria-label={t("back")}
            >
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          ) : (
            <span className="w-10" />
          )}
          <h2 className="public-nav-title">
            {current.view === "user"
              ? t("profile")
              : current.view === "wishlist"
              ? (current.wishlistTitle ?? t("wishlists"))
              : current.view === "wish"
              ? (current.wishTitle ?? t("wishes"))
              : t("copyToMyWishlist")}
          </h2>
          <span className="w-10" />
        </div>

        <div className="public-nav-viewport">
          {guardDecision === "startup" ? (
            <div className="public-nav-frame">
              <div className="public-nav-content">
                <AuthRequiredPanel forcePending />
              </div>
            </div>
          ) : guardDecision === "auth_required" ? (
            <div className="public-nav-frame">
              <div className="public-nav-content">
                <AuthRequiredPanel />
              </div>
            </div>
          ) : null}
          {guardDecision === "app" && accessToken ? (
            <>
          {previousFrame ? (
            <div
              className={`public-nav-frame public-nav-exit-${direction}`}
              key={`previous-${previousFrame.view}-${previousFrame.wishlistId ?? ""}-${previousFrame.wishId ?? ""}`}
            >
              {renderFrame(previousFrame)}
            </div>
          ) : null}
          <div
            className={`public-nav-frame ${previousFrame ? `public-nav-enter-${direction}` : ""}`}
            key={`current-${current.view}-${current.wishlistId ?? ""}-${current.wishId ?? ""}`}
            onAnimationEnd={() => setPreviousFrame(null)}
          >
            {renderFrame(current)}
          </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

type PublicUserViewProps = {
  username: string;
  profileToken?: string | null;
  initialUser?: UserProfileResponse | null;
  onOpenWishlist: (wishlistId: string, title?: string) => void;
  onClose: () => void;
};

/**
 * show public profile
 */
function PublicUserView({ username, profileToken, initialUser, onOpenWishlist, onClose }: PublicUserViewProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const queryClient = useQueryClient();
  const profileQuery = useUserProfileQuery(username, profileToken);
  const wishlistsQuery = useUserWishlistsQuery(username, profileToken);
  const profile = profileQuery.data ?? initialUser;
  const followMutation = useFollowMutation(username, profileToken);
  const wishlists = wishlistsQuery.data?.items ?? [];
  const { t } = useTranslation();

  useEffect(() => {
    if (!accessToken || !username) return;
    queryClient.prefetchQuery({
      queryKey: [...userQueryKeys.profile(username), accessToken, profileToken] as const,
      queryFn: () => getUserProfile(accessToken, username, profileToken),
      staleTime: 30 * 1000,
    });
    queryClient.prefetchQuery({
      queryKey: [...wishlistQueryKeys.user(username), accessToken, profileToken] as const,
      queryFn: () => listUserWishlists(accessToken, username, profileToken),
    });
  }, [accessToken, profileToken, queryClient, username]);

  function handleWishlistHover(wishlistId: string) {
    if (!accessToken) return;
    queryClient.prefetchQuery({
      queryKey: [...wishlistQueryKeys.detail(wishlistId), accessToken] as const,
      queryFn: () => getWishlist(accessToken, wishlistId),
    });
    queryClient.prefetchQuery({
      queryKey: wishQueryKeys.list(wishlistId),
      queryFn: () => listWishes(accessToken, wishlistId),
    });
  }

  function formatBirthday(raw: string | null | undefined) {
    if (!raw) return null;
    try {
      const [y, m, d] = raw.split("-");
      const months = t("months").split(",");
      return `${parseInt(d, 10)} ${months[parseInt(m, 10) - 1]} ${y}`;
    } catch {
      return null;
    }
  }

  return (
    <div className="public-nav-content">
      {profileQuery.isLoading && !profile ? <ProfileSkeleton /> : null}
      {profileQuery.isError ? <p className="text-sm text-destructive text-center py-4">{t("unableToLoadProfile")}</p> : null}
      {profile ? (
        <div className="public-profile-card flex justify-between items-center gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <UserAvatar user={profile} />
            <div className="min-w-0">
              <h3 className="text-base font-bold text-foreground truncate">
                {profile.first_name} {profile.last_name || ""}
              </h3>
              {profile.username ? (
                <a
                  href={`https://t.me/${profile.username}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => {
                    const win = window as unknown as { Telegram?: { WebApp?: { openTelegramLink?: (url: string) => void } } };
                    if (typeof window !== "undefined" && win.Telegram?.WebApp?.openTelegramLink) {
                      e.preventDefault();
                      win.Telegram.WebApp.openTelegramLink(`https://t.me/${profile.username}`);
                    }
                  }}
                  className="text-xs text-primary hover:underline cursor-pointer"
                >
                  @{profile.username}
                </a>
              ) : null}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 flex-shrink-0">
            {!profile.is_self && profile.username ? (
              <button
                type="button"
                className={`h-9 px-4 rounded-xl text-xs font-extrabold transition-all active:scale-[0.98] ${
                  profile.is_following
                    ? "border border-border bg-background text-primary"
                    : "theme-press-primary bg-primary text-white"
                }`}
                disabled={followMutation.isPending}
                onClick={() => {
                  const nextFollowing = !profile.is_following;
                  followMutation.mutate(nextFollowing, {
                    onSuccess: () => {
                      if (!nextFollowing) onClose();
                    },
                  });
                }}
              >
                {profile.is_following ? t("following") : t("follow")}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {profile?.birthday ? (
        <div className="mx-2 mt-2 rounded-2xl border border-border bg-muted/10 px-4 py-3">
          <span className="block text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("birthday")}</span>
          <span className="block text-sm font-semibold text-foreground mt-1">{formatBirthday(profile.birthday)}</span>
        </div>
      ) : null}

      <section className="flex flex-col mt-1 px-2">
        <div className="px-4 py-3 border-b-2 border-border">
          <h3 className="text-sm font-bold text-foreground">{t("publicWishlists")}</h3>
        </div>
        {wishlistsQuery.isLoading && wishlists.length === 0 ? <ListSkeleton /> : null}
        {!wishlistsQuery.isLoading && wishlists.length === 0 ? (
          <p className="text-sm text-muted text-center py-6">{t("noPublicWishlists")}</p>
        ) : null}
        {wishlists.map((wishlist) => (
          <PublicWishlistRow
            key={wishlist.id}
            wishlist={wishlist}
            onOpen={(id) => onOpenWishlist(id, wishlist.title)}
            onPrefetch={handleWishlistHover}
          />
        ))}
      </section>
    </div>
  );
}

type PublicWishlistRowProps = {
  wishlist: Wishlist;
  onOpen: (wishlistId: string, title?: string) => void;
  onPrefetch: (wishlistId: string) => void;
};

/**
 * public wishlist row
 */
function PublicWishlistRow({ wishlist, onOpen, onPrefetch }: PublicWishlistRowProps) {
  const { data: wishesData } = useWishesQuery(wishlist.id);
  const { description } = parseWishlistDescription(wishlist.description);
  const { t } = useTranslation();
  const wishesCount = wishesData?.items.length ?? 0;
  const countText = wishesCount === 0
    ? t("noWishes")
    : wishesCount === 1
      ? `1 ${t("wishCountLabel")}`
      : `${wishesCount} ${t("wishesCountLabel")}`;

  return (
    <button
      type="button"
      className="public-row-button"
      onClick={() => onOpen(wishlist.id, wishlist.title)}
      onFocus={() => onPrefetch(wishlist.id)}
      onMouseEnter={() => onPrefetch(wishlist.id)}
      onTouchStart={() => onPrefetch(wishlist.id)}
    >
      <div className="min-w-0 text-left">
        <span className="font-semibold text-sm text-foreground line-clamp-1">{wishlist.title}</span>
        {description ? <span className="text-xs text-muted line-clamp-1 mt-1">{description}</span> : null}
      </div>
      <div className="flex items-center gap-1 text-primary font-medium text-xs shrink-0">
        <span>{countText}</span>
        <ChevronIcon />
      </div>
    </button>
  );
}

type PublicWishlistViewProps = {
  wishlistId: string;
  onOpenWish: (wishlistId: string, wishId: string, title?: string) => void;
};

/**
 * show public wishlist
 */
function PublicWishlistView({ wishlistId, onOpenWish }: PublicWishlistViewProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const queryClient = useQueryClient();
  const wishlistQuery = useWishlistQuery(wishlistId);
  const wishesQuery = useWishesQuery(wishlistId);
  const wishlist = wishlistQuery.data;
  const wishes = wishesQuery.data?.items ?? [];
  const parsed = parseWishlistDescription(wishlist?.description);
  const hasUploadedCover = parsed.coverStyle.startsWith("data:") || parsed.coverStyle.startsWith("http");
  const coverStyle = getWishlistCoverStyle({
    coverStyle: parsed.coverStyle,
    fallback: { angle: 135, a: "#8b5cf6", b: "#60a5fa", c: "#34d399", d: "#f472b6" },
  });
  const { t } = useTranslation();

  function handleWishHover() {
    if (!accessToken) return;
    queryClient.prefetchQuery({
      queryKey: wishQueryKeys.list(wishlistId),
      queryFn: () => listWishes(accessToken, wishlistId),
    });
  }

  return (
    <div className="public-nav-content">
      {wishlistQuery.isError ? <p className="text-sm text-destructive text-center py-4">{t("unableToLoadWishlists")}</p> : null}
      {wishlist && hasUploadedCover ? (
        <section className="public-wishlist-cover" style={coverStyle}>
          <div className="relative z-10 mt-auto">
            {parsed.description ? <p className="text-sm text-white/85 mt-2 line-clamp-3">{parsed.description}</p> : null}
          </div>
        </section>
      ) : null}

      <section className="flex flex-col mt-4 px-2">
        {wishesQuery.isLoading && wishes.length === 0 ? <ListSkeleton /> : null}
        {!wishesQuery.isLoading && wishes.length === 0 ? (
          <p className="text-sm text-muted text-center py-6">{t("noPublicWishes")}</p>
        ) : null}
        {wishes.map((wish) => (
          <PublicWishRow
            key={wish.id}
            wish={wish}
            onOpen={() => onOpenWish(wishlistId, wish.id, wish.title)}
            onPrefetch={handleWishHover}
          />
        ))}
      </section>
    </div>
  );
}

type PublicWishRowProps = {
  wish: Wish;
  onOpen: () => void;
  onPrefetch: () => void;
};

/**
 * public wish row
 */
function PublicWishRow({ wish, onOpen, onPrefetch }: PublicWishRowProps) {
  const isCompleted = wish.status === "completed";
  const reservationStatus = useReservationStatusQuery(wish.id);
  const isBooked = reservationStatus.data?.is_reserved ?? false;
  return (
    <button
      type="button"
      className="public-row-button"
      onClick={onOpen}
      onFocus={onPrefetch}
      onMouseEnter={onPrefetch}
      onTouchStart={onPrefetch}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="relative w-12 h-12 rounded-2xl overflow-hidden shrink-0 border border-border">
          <WishImageThumb id={wish.id} title={wish.title} imageUrl={wish.images?.[0]?.url} className="w-full h-full object-cover" />
          {isCompleted ? (
            <div className="absolute inset-0 flex items-center justify-center bg-emerald-500/30">
              <svg className="w-5 h-5 text-green-300" fill="currentColor" viewBox="0 0 24 24">
                <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
              </svg>
            </div>
          ) : null}
          {!isCompleted && isBooked ? (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-700/35">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24">
                <rect x="6" y="10" width="12" height="9" rx="2" />
                <path strokeLinecap="round" d="M9 10V7a3 3 0 0 1 6 0v3" />
              </svg>
            </div>
          ) : null}
        </div>
        <div className={`min-w-0 text-left ${!isCompleted && isBooked ? "opacity-50" : ""}`}>
          <span className="font-semibold text-sm text-foreground line-clamp-1">{wish.title}</span>
          {wish.description ? <span className="text-xs text-muted line-clamp-1 mt-1">{wish.description}</span> : null}
        </div>
      </div>
      <ChevronIcon />
    </button>
  );
}

type PublicWishViewProps = {
  wishlistId: string;
  wishId: string;
};

/**
 * show public wish
 */
function PublicWishView({ wishlistId, wishId }: PublicWishViewProps) {
  const wishesQuery = useWishesQuery(wishlistId);
  const wish = useMemo(
    () => wishesQuery.data?.items.find((item) => item.id === wishId) ?? null,
    [wishId, wishesQuery.data?.items],
  );
  const { t } = useTranslation();
  const reservationStatus = useReservationStatusQuery(wishId);
  const createReservation = useCreateReservationMutation(wishlistId);
  const status = reservationStatus.data;
  const isReserved = status?.is_reserved ?? false;
  const isBusy = createReservation.isPending;
  const isCompleted = wish?.status === "completed";

  function handleBook() {
    if (!isReserved && !isCompleted) {
      createReservation.mutate(wishId);
    }
  }

  function bookButtonLabel() {
    if (createReservation.isPending) return t("reserving");
    if (isReserved) return t("wishReservedByOther");
    return t("book");
  }

  if (wishesQuery.isLoading && !wish) {
    return <WishSkeleton />;
  }

  if (!wish) {
    return <p className="text-sm text-muted text-center py-6">{t("unableToLoadWishes")}</p>;
  }

  return (
    <div className="public-nav-content">
      <section className="flex flex-col items-center gap-4">
        <div className="public-wish-gallery relative">
          <WishImageThumb id={wish.id} title={wish.title} imageUrl={wish.images?.[0]?.url} className={`w-full h-full object-cover ${isCompleted ? "wish-image-fulfilled" : ""}`} />
        </div>
        {isCompleted ? (
          <p className="text-sm font-bold text-green-500">{t("wishFulfilled")}</p>
        ) : null}
        {wish.images.length > 1 ? (
          <div className="grid grid-cols-4 gap-2 w-full">
            {wish.images.slice(0, 4).map((image) => (
              <div key={image.id} className="aspect-square rounded-xl overflow-hidden border border-border">
                <WishImageThumb id={wish.id} title={wish.title} imageUrl={image.url} className="w-full h-full object-cover" />
              </div>
            ))}
          </div>
        ) : null}
        <div className="w-full text-center">
          {wish.price ? <p className="text-lg font-extrabold text-primary mt-1">{formatPrice(wish.price, wish.currency)}</p> : null}
        </div>
      </section>

      {!isCompleted ? <section className="flex flex-col gap-2 w-full mt-4 px-4">
        <button
          type="button"
          className="public-action-button public-action-primary"
          onClick={handleBook}
          disabled={isBusy || isReserved}
        >
          {bookButtonLabel()}
        </button>
      </section> : null}

      {wish.description ? (
        <section className="flex flex-col px-4 mt-2">
          <div className="w-full rounded-2xl border border-border bg-muted/10 px-4 py-3">
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-muted">{t("descriptionLabel")}</p>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-foreground">{wish.description}</p>
          </div>
        </section>
      ) : null}
    </div>
  );
}

/**
 * format wish price
 */
function formatPrice(price: string, currency: string | null) {
  return `${price}${currency ? ` ${currency}` : ""}`;
}

/**
 * chevron icon
 */
function ChevronIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-muted/60 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

/**
 * profile skeleton
 */
function ProfileSkeleton() {
  return (
    <div className="public-profile-card">
      <div className="public-skeleton h-12 w-12 rounded-full" />
      <div className="flex-1 min-w-0">
        <div className="public-skeleton h-4 w-32 rounded-md" />
        <div className="public-skeleton h-3 w-20 rounded-md mt-2" />
      </div>
    </div>
  );
}


/**
 * wish skeleton
 */
function WishSkeleton() {
  return (
    <div className="public-nav-content">
      <div className="public-skeleton public-wish-gallery" />
      <div className="public-skeleton h-5 w-40 rounded-md mx-auto" />
      <ListSkeleton />
    </div>
  );
}

/**
 * list skeleton
 */
function ListSkeleton() {
  return (
    <div className="p-4 flex flex-col gap-3">
      <div className="public-skeleton h-12 w-full rounded-xl" />
      <div className="public-skeleton h-12 w-full rounded-xl" />
      <div className="public-skeleton h-12 w-full rounded-xl" />
    </div>
  );
}

type PublicCopyViewProps = {
  wishlistId: string;
  wishId: string;
  onCopySuccess: () => void;
};

/**
 * public copy view
 */
function PublicCopyView({ wishlistId, wishId, onCopySuccess }: PublicCopyViewProps) {
  const { t } = useTranslation();
  const wishlistsQuery = useWishlistsQuery();
  const wishlists = wishlistsQuery.data?.items ?? [];
  const copyWishMutation = useCopyWishMutation(wishlistId);

  return (
    <div className="public-nav-content">
      <section className="flex flex-col mt-2 px-2">
        {wishlistsQuery.isLoading ? <p className="text-sm text-muted py-2 text-center">{t("loadingWishlists")}</p> : null}
        {!wishlistsQuery.isLoading && wishlists.length === 0 ? (
          <p className="text-sm text-muted py-2 text-center">{t("createWishlistBeforeCopy")}</p>
        ) : null}
        {wishlists.length > 0 ? (
          <div className="flex flex-col divide-y divide-border border-y border-border">
            {wishlists.map((wl) => (
              <button
                key={wl.id}
                type="button"
                className="flex items-center justify-between py-4 px-2 text-left w-full cursor-pointer hover:bg-muted/5 transition-colors"
                disabled={copyWishMutation.isPending}
                onClick={() => {
                  copyWishMutation.mutate(
                    { wishId, wishlistId: wl.id },
                    { onSuccess: onCopySuccess }
                  );
                }}
              >
                <span className="text-sm font-semibold text-foreground line-clamp-1">{wl.title}</span>
                {copyWishMutation.isPending ? <span className="auth-loading-spinner copy-row-spinner shrink-0 ml-4" /> : null}
              </button>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
