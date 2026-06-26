// public wishlist navigator
"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { useReservationStatusQuery, useCreateReservationMutation } from "@/features/reservations/hooks";
import { ViewGroupGiftContent, type ActionMode } from "@/features/group-gifts/view-group-gift-sheet";
import { CreateGroupGiftContent } from "@/features/group-gifts/create-group-gift-sheet";
import { UserAvatar } from "@/features/users/user-avatar";
import { getUserProfile, getUserProfileById, type UserProfileResponse } from "@/features/users/api";
import { userQueryKeys, useFollowMutation, useFollowByIdMutation, useUserProfileQuery, useUserProfileByIdQuery, useUserWishlistsByIdQuery } from "@/features/users/hooks";
import { getWishlist, listUserWishlists } from "@/features/wishlists/api";
import { getUserWishlistsById } from "@/features/users/api";
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
  userId?: string | null;
  profileToken?: string | null;
  initialUser?: UserProfileResponse | null;
  initialWishlistId?: string | null;
  initialWishId?: string | null;
  shareToken?: string | null;
  onClose: () => void;
};

type NavigationView = "user" | "wishlist" | "wish" | "copy" | "createGroupGift" | "viewGroupGift";
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
  userId,
  profileToken,
  initialUser,
  initialWishlistId,
  initialWishId,
  shareToken,
  onClose,
}: PublicWishlistNavigatorProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const [active, setActive] = useState(false);
  const [stack, setStack] = useState<NavigationFrame[]>([{ view: "user" }]);
  const [direction, setDirection] = useState<NavigationDirection>("forward");
  const [previousFrame, setPreviousFrame] = useState<NavigationFrame | null>(null);
  const [groupGiftActionMode, setGroupGiftActionMode] = useState<ActionMode>("overview");
  const [groupGiftFocusMode, setGroupGiftFocusMode] = useState(false);
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
      setGroupGiftActionMode("overview");
      setGroupGiftFocusMode(false);
    }
  }, [initialWishlistId, initialWishId, open, username, userId]);

  if (!open || (!username && !userId)) return null;

  const activeUserId = userId ?? null;
  const activeUsername = username ? username.trim().replace(/^@/, "") : null;
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
    if (current.view === "viewGroupGift" && groupGiftActionMode !== "overview") {
      return;
    }
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

  function handleCreateGroupGiftOpen(wishlistId: string, wishId: string) {
    setDirection("forward");
    setPreviousFrame(current);
    setStack((currentStack) => [...currentStack, { view: "createGroupGift", wishlistId, wishId }]);
  }

  function handleViewGroupGiftOpen(wishlistId: string, wishId: string) {
    setGroupGiftActionMode("overview");
    setDirection("forward");
    setPreviousFrame(current);
    setStack((currentStack) => [...currentStack, { view: "viewGroupGift", wishlistId, wishId }]);
  }

  function groupGiftTitle() {
    if (groupGiftActionMode === "purchase") return "";
    if (groupGiftActionMode === "contribute") return t("makeContribution");
    if (groupGiftActionMode === "editPayment") return t("editPaymentDetails");
    if (groupGiftActionMode === "cancel") return "";
    if (groupGiftActionMode === "unbook") return "";
    if (groupGiftActionMode === "removeContribution") return t("removeContribution");
    return t("groupGift");
  }

  function renderFrame(frame: NavigationFrame) {
    if (frame.view === "user") {
      return (
        <PublicUserView
          username={activeUsername}
          userId={activeUserId}
          profileToken={profileToken}
          initialUser={initialUser}
          onOpenWishlist={handleWishlistOpen}
          onClose={handleClose}
        />
      );
    }

    if (frame.view === "wishlist" && frame.wishlistId) {
      return <PublicWishlistView wishlistId={frame.wishlistId} shareToken={shareToken} onOpenWish={handleWishOpen} />;
    }

    if (frame.view === "wish" && frame.wishlistId && frame.wishId) {
      return (
        <PublicWishView
          wishlistId={frame.wishlistId}
          wishId={frame.wishId}
          shareToken={shareToken}
          onOpenCreateGroupGift={handleCreateGroupGiftOpen}
          onOpenViewGroupGift={handleViewGroupGiftOpen}
        />
      );
    }

    if (frame.view === "copy" && frame.wishlistId && frame.wishId) {
      return <PublicCopyView wishlistId={frame.wishlistId} wishId={frame.wishId} onCopySuccess={handleCopySuccess} />;
    }

    if (frame.view === "createGroupGift" && frame.wishlistId && frame.wishId) {
      return (
        <PublicCreateGroupGiftView
          wishId={frame.wishId}
          onDone={handleBack}
          onFocusModeChange={setGroupGiftFocusMode}
        />
      );
    }

    if (frame.view === "viewGroupGift" && frame.wishlistId && frame.wishId) {
      return (
        <PublicViewGroupGiftView
          wishId={frame.wishId}
          shareToken={shareToken}
          onDone={handleBack}
          actionMode={groupGiftActionMode}
          onActionModeChange={setGroupGiftActionMode}
          onFocusModeChange={setGroupGiftFocusMode}
        />
      );
    }

    return null;
  }

  return (
    <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={handleClose}>
      <div
        className={`modal-sheet public-nav-sheet ${active ? "visible" : ""} ${groupGiftFocusMode ? "keyboard-focus-mode" : ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-handle" />
        <div className={`public-nav-header ${groupGiftFocusMode ? "modal-focus-collapsed" : "modal-focus-section"}`}>
          {stack.length > 1 && !(current.view === "viewGroupGift" && groupGiftActionMode !== "overview") ? (
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
              : current.view === "createGroupGift"
              ? t("createGroupGift")
              : current.view === "viewGroupGift"
              ? groupGiftTitle()
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
  username: string | null;
  userId?: string | null;
  profileToken?: string | null;
  initialUser?: UserProfileResponse | null;
  onOpenWishlist: (wishlistId: string, title?: string) => void;
  onClose: () => void;
};

/**
 * show public profile
 */
function PublicUserView({ username, userId, profileToken, initialUser, onOpenWishlist, onClose }: PublicUserViewProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const queryClient = useQueryClient();
  const profileByIdQuery = useUserProfileByIdQuery(userId ?? null, profileToken);
  const profileByUsernameQuery = useUserProfileQuery(username ?? "", profileToken);
  const wishlistsByIdQuery = useUserWishlistsByIdQuery(userId ?? null, profileToken);
  const wishlistsByUsernameQuery = useUserWishlistsQuery(username ?? "", profileToken);
  const profileQuery = userId ? profileByIdQuery : profileByUsernameQuery;
  const wishlistsQuery = userId ? wishlistsByIdQuery : wishlistsByUsernameQuery;
  const profile = profileQuery.data ?? initialUser;
  const followByIdMutation = useFollowByIdMutation(userId ?? "", profileToken);
  const followByUsernameMutation = useFollowMutation(username ?? "", profileToken);
  const followMutation = userId ? followByIdMutation : followByUsernameMutation;
  const wishlists = wishlistsQuery.data?.items ?? [];
  const { t } = useTranslation();

  useEffect(() => {
    if (!accessToken) return;
    if (userId) {
      const profileKey = profileToken
        ? ([...userQueryKeys.profileById(userId), profileToken] as const)
        : userQueryKeys.profileById(userId);
      const wishlistsKey = profileToken
        ? ([...userQueryKeys.wishlistsById(userId), profileToken] as const)
        : userQueryKeys.wishlistsById(userId);
      queryClient.prefetchQuery({
        queryKey: profileKey,
        queryFn: () => getUserProfileById(accessToken, userId, profileToken),
        staleTime: 5 * 60 * 1000,
      });
      queryClient.prefetchQuery({
        queryKey: wishlistsKey,
        queryFn: () => getUserWishlistsById(accessToken, userId, profileToken),
        staleTime: 2 * 60 * 1000,
      });
    } else if (username) {
      const profileKey = profileToken
        ? ([...userQueryKeys.profile(username), profileToken] as const)
        : userQueryKeys.profile(username);
      const wishlistsKey = profileToken
        ? ([...wishlistQueryKeys.user(username), profileToken] as const)
        : wishlistQueryKeys.user(username);
      queryClient.prefetchQuery({
        queryKey: profileKey,
        queryFn: () => getUserProfile(accessToken, username, profileToken),
        staleTime: 5 * 60 * 1000,
      });
      queryClient.prefetchQuery({
        queryKey: wishlistsKey,
        queryFn: () => listUserWishlists(accessToken, username, profileToken),
        staleTime: 2 * 60 * 1000,
      });
    }
  }, [accessToken, profileToken, queryClient, username, userId]);

  function handleWishlistHover(wishlistId: string) {
    if (!accessToken) return;
    queryClient.prefetchQuery({
      queryKey: wishlistQueryKeys.detail(wishlistId),
      queryFn: () => getWishlist(accessToken, wishlistId),
      staleTime: 2 * 60 * 1000,
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
              {profile.birthday ? (
                <p className="text-xs text-muted mt-0.5 flex items-center gap-1">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 12 20 22 4 22 4 12" />
                    <rect x="2" y="7" width="20" height="5" />
                    <line x1="12" y1="22" x2="12" y2="7" />
                    <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z" />
                    <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z" />
                  </svg>
                  {new Date(profile.birthday).toLocaleDateString(undefined, { month: "long", day: "numeric" })}
                </p>
              ) : null}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 flex-shrink-0">
            {!profile.is_self ? (
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
  shareToken?: string | null;
  onOpenWish: (wishlistId: string, wishId: string, title?: string) => void;
};

/**
 * show public wishlist
 */
function PublicWishlistView({ wishlistId, shareToken, onOpenWish }: PublicWishlistViewProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const queryClient = useQueryClient();
  const wishlistQuery = useWishlistQuery(wishlistId, shareToken);
  const wishesQuery = useWishesQuery(wishlistId, true, shareToken, false);
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
      queryKey: [...wishQueryKeys.list(wishlistId), shareToken] as const,
      queryFn: () => listWishes(accessToken, wishlistId, shareToken),
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
            shareToken={shareToken}
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
  shareToken?: string | null;
  onOpen: () => void;
  onPrefetch: () => void;
};

/**
 * public wish row
 */
function PublicWishRow({ wish, shareToken, onOpen, onPrefetch }: PublicWishRowProps) {
  const isCompleted = wish.status === "completed";
  const reservationStatus = useReservationStatusQuery(wish.id, shareToken);
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
          <WishImageThumb id={wish.id} title={wish.title} imageUrl={wish.images?.[0]?.thumbnail_url ?? wish.images?.[0]?.medium_url} className="w-full h-full object-cover" />
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
          <span className="font-semibold text-sm text-foreground line-clamp-2">{wish.title}</span>
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
  shareToken?: string | null;
  onOpenCreateGroupGift: (wishlistId: string, wishId: string) => void;
  onOpenViewGroupGift: (wishlistId: string, wishId: string) => void;
};

/**
 * show public wish
 */
function PublicWishView({
  wishlistId,
  wishId,
  shareToken,
  onOpenCreateGroupGift,
  onOpenViewGroupGift,
}: PublicWishViewProps) {
  const wishesQuery = useWishesQuery(wishlistId, true, shareToken, false);
  const wish = useMemo(
    () => wishesQuery.data?.items.find((item) => item.id === wishId) ?? null,
    [wishId, wishesQuery.data?.items],
  );
  const { t } = useTranslation();
  const reservationStatus = useReservationStatusQuery(wishId, shareToken);
  const createReservation = useCreateReservationMutation(wishlistId, shareToken);
  const status = reservationStatus.data;
  const isReserved = status?.is_reserved ?? false;
  const isBusy = createReservation.isPending;
  const isCompleted = wish?.status === "completed";
  const hasActiveGroupGift =
    wish?.group_gift?.status === "active" || status?.has_active_group_gift === true;

  function handleBook() {
    if (!isReserved && !isCompleted) {
      createReservation.mutate(wishId);
    }
  }

  function bookButtonLabel() {
    if (createReservation.isPending) return t("reserving");
    if (isReserved) return t("wishReservedByOther");
    if (wish?.price) return `${t("book")} · ${formatPrice(wish.price, wish.currency)}`;
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
      <section className="flex flex-col items-center gap-3">
        <div className="public-wish-gallery relative">
          <WishImageThumb id={wish.id} title={wish.title} imageUrl={wish.images?.[0]?.medium_url ?? wish.images?.[0]?.thumbnail_url} className={`w-full h-full object-cover ${isCompleted ? "wish-image-fulfilled" : ""}`} />
        </div>
        {isCompleted ? (
          <p className="text-sm font-bold text-green-500">{t("wishFulfilled")}</p>
        ) : null}
        {wish.images.length > 1 ? (
          <div className="grid grid-cols-4 gap-2 w-full">
            {wish.images.slice(0, 4).map((image) => (
              <div key={image.id} className="aspect-square rounded-xl overflow-hidden border border-border">
                <WishImageThumb id={wish.id} title={wish.title} imageUrl={image.thumbnail_url ?? image.medium_url} className="w-full h-full object-cover" />
              </div>
            ))}
          </div>
        ) : null}
      </section>

      {!isCompleted ? (
        <section className="flex flex-col gap-2 w-full mt-3 px-4">
          {/* Slot 1 — primary action button */}
          {hasActiveGroupGift ? (
            wish.group_gift?.is_organizer || wish.group_gift?.is_contributor ? null : (
              <button
                type="button"
                className="public-action-button public-action-primary"
                onClick={() => onOpenViewGroupGift(wishlistId, wishId)}
              >
                {t("joinGiftButton")}
              </button>
            )
          ) : (
            <>
              <button
                type="button"
                className="public-action-button public-action-primary"
                onClick={handleBook}
                disabled={isBusy || isReserved}
              >
                {bookButtonLabel()}
              </button>
              {!isReserved ? (
                <button
                  type="button"
                  className="public-action-button border border-border bg-background text-primary"
                  onClick={() => onOpenCreateGroupGift(wishlistId, wishId)}
                >
                  {t("createGroupGift")}
                </button>
              ) : null}
            </>
          )}

          {/* Slot 2 — group gift progress row */}
          {wish.group_gift ? (
            <button
              type="button"
              className="w-full text-left rounded-xl border border-border bg-muted/5 px-3 py-2.5 flex flex-col gap-1.5"
              onClick={() => onOpenViewGroupGift(wishlistId, wishId)}
            >
              <div className="flex justify-between items-center text-xs text-muted">
                <span>{t("groupGift")}</span>
                <span>
                  {wish.group_gift.status === "cancelled"
                    ? t("giftCancelled")
                    : wish.group_gift.status === "completed" || wish.group_gift.percent_complete >= 100
                    ? t("giftComplete")
                    : t("giftProgress").replace("{percent}", String(wish.group_gift.percent_complete))}
                </span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-muted/20 overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-700 ease-out"
                  style={{ width: `${Math.min(100, wish.group_gift.percent_complete)}%` }}
                />
              </div>
            </button>
          ) : null}

          {wish.original_product_url ? (
            <a
              href={wish.original_product_url}
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
      ) : (
        wish.original_product_url ? (
          <section className="flex flex-col items-center px-4 mt-3">
            <a
              href={wish.original_product_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-muted hover:text-foreground transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              {t("openProductPage") ?? "Open wish's page"}
            </a>
          </section>
        ) : null
      )}

      {wish.description ? (
        <section className="px-4 mt-2">
          <div className="rounded-xl border border-border bg-muted/5 px-3 py-2.5 text-left">
            <h4 className="text-[10px] font-extrabold uppercase tracking-wider text-muted mb-1.5">
              {t("descriptionLabel")}
            </h4>
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/80">
            {wish.description}
            </p>
          </div>
        </section>
      ) : null}

    </div>
  );
}

type PublicCreateGroupGiftViewProps = {
  wishId: string;
  onDone: () => void;
  onFocusModeChange: (isFocus: boolean) => void;
};

function PublicCreateGroupGiftView({ wishId, onDone, onFocusModeChange }: PublicCreateGroupGiftViewProps) {
  return (
    <div className="public-nav-content px-4">
      <CreateGroupGiftContent
        wishId={wishId}
        showTitle={false}
        onCancel={onDone}
        onClose={onDone}
        onFocusModeChange={onFocusModeChange}
      />
    </div>
  );
}

type PublicViewGroupGiftViewProps = {
  wishId: string;
  shareToken?: string | null;
  onDone: () => void;
  actionMode: ActionMode;
  onActionModeChange: (mode: ActionMode) => void;
  onFocusModeChange: (isFocus: boolean) => void;
};

function PublicViewGroupGiftView({
  wishId,
  shareToken,
  onDone,
  actionMode,
  onActionModeChange,
  onFocusModeChange,
}: PublicViewGroupGiftViewProps) {
  return (
    <div className="public-nav-content px-4">
      <ViewGroupGiftContent
        wishId={wishId}
        shareToken={shareToken}
        showTitle={false}
        onClose={onDone}
        actionMode={actionMode}
        onActionModeChange={onActionModeChange}
        onFocusModeChange={onFocusModeChange}
      />
    </div>
  );
}


/**
 * format wish price
 */
function formatPrice(price: string, currency: string | null) {
  const num = parseFloat(price);
  const formatted = isNaN(num)
    ? price.replace(".", ",")
    : (Number.isInteger(num) ? String(num) : num.toFixed(2).replace(".", ","));
  return `${formatted}${currency ? ` ${currency}` : ""}`;
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
