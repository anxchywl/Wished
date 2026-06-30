"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  hideBackButton,
  isBackButtonMounted,
  isBackButtonSupported,
  mountBackButton,
  offBackButtonClick,
  onBackButtonClick,
  showBackButton,
} from "@telegram-apps/sdk-react";

import { QueryProvider } from "@/lib/query/query-provider";
import { TelegramProvider, useTelegram } from "@/lib/telegram/telegram-provider";
import { useUIStore } from "@/stores/ui-store";
import { useAuthStore } from "@/stores/auth-store";

import { useTelegramLoginMutation } from "@/features/auth";
import { useWishlistsQuery } from "@/features/wishlists/hooks";
import { listWishes } from "@/features/wishes/api";
import { wishQueryKeys } from "@/features/wishes/query-keys";
import { listFollowing } from "@/features/users/api";
import { userQueryKeys, useFollowingQuery } from "@/features/users/hooks";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { CoverHeader } from "@/components/ui/cover-header";
import { BookingVisibilityHeaderButton } from "@/features/users/user-discovery-manager";
import { useBookedWishesQuery } from "@/features/reservations/hooks";
import { BottomNav } from "@/components/ui/bottom-nav";
import { logStartup } from "@/lib/debug/startup-log";
import { extractTgUserIdFromInitData } from "@/lib/telegram/capture-init-data";
import { decodeProfileStartParam, decodeWishlistStartParam } from "@/lib/telegram/start-param";
import { isAuthPending } from "@/stores/auth-store";
import { clearPersistedCache } from "@/lib/query/cache-persister";

type AppProvidersProps = {
  children: ReactNode;
};

function BlockedScreen() {
  const { t } = useTranslation();
  const blockReason = useAuthStore((state) => state.blockReason);
  
  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center bg-background z-[9999] px-8 text-center gap-4">
      <div style={{ fontSize: 48 }}>🚫</div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: "var(--tg-theme-text-color)" }}>
        {t("accountRestrictedTitle")}
      </h1>
      <p style={{ fontSize: 15, color: "var(--tg-theme-hint-color)", lineHeight: 1.5 }}>
        {blockReason ? blockReason : t("accountRestrictedBody")}
      </p>
      <p style={{ fontSize: 13, color: "var(--tg-theme-hint-color)", opacity: 0.8, marginTop: 16 }}>
        {t("accountRestrictedSupport") ?? "If you believe this is a mistake, please contact support."}
      </p>
    </div>
  );
}

/**
 * persistent layout wrapper
 */
function PersistentLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { t } = useTranslation();
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const setAccessToken = useAuthStore((state) => state.setAccessToken);
  const setAuthStatus = useAuthStore((state) => state.setAuthStatus);
  const setAppReady = useAuthStore((state) => state.setAppReady);
  const tgUserId = useAuthStore((state) => state.tgUserId);
  const setTgUserId = useAuthStore((state) => state.setTgUserId);
  const prepareAccountSwitch = useAuthStore((state) => state.prepareAccountSwitch);

  const { initDataRaw, isReady, error: telegramError } = useTelegram();
  const loginMutation = useTelegramLoginMutation();
  const wishlistsQuery = useWishlistsQuery();
  const queryClient = useQueryClient();
  const [gateExpired, setGateExpired] = useState(false);
  const [initialWishesLoaded, setInitialWishesLoaded] = useState(false);
  const lastLoginInitDataRef = useRef<string | null>(null);
  const followingQuery = useFollowingQuery();
  const bookedWishesQuery = useBookedWishesQuery();

  const loginMutationRef = useRef(loginMutation);
  loginMutationRef.current = loginMutation;
  const isWishlistsRoute = pathname === "/" || pathname === "/wishlists";
  const initialWishlistsSettled = wishlistsQuery.isSuccess || wishlistsQuery.isError;

  // Safety valve: never block the app forever if auth hangs
  useEffect(() => {
    const id = setTimeout(() => setGateExpired(true), 10_000);
    return () => clearTimeout(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    logStartup("app mounted", authStatus, {
      hasAccessToken: Boolean(accessToken),
      hasInitDataRaw: Boolean(initDataRaw),
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isReady) {
      // warm start: already have a token, keep authStatus and queries enabled
      if (!accessToken && authStatus !== "authenticated") setAuthStatus("waiting_for_telegram");
      return;
    }

    if (initDataRaw && authStatus === "waiting_for_telegram") {
      setAuthStatus("telegram_ready");
    }

    const currentTgUserId = extractTgUserIdFromInitData(initDataRaw ?? "");

    // if account changed (or a stale token has no matching stored user), clear everything
    if (currentTgUserId && accessToken && currentTgUserId !== tgUserId) {
      clearPersistedCache();
      queryClient.clear();
      prepareAccountSwitch(currentTgUserId);
      setInitialWishesLoaded(false);
      lastLoginInitDataRef.current = null;
      loginMutationRef.current.reset();
      return;
    }

    if (currentTgUserId && !tgUserId) {
      setTgUserId(currentTgUserId);
    }

    if (initDataRaw && !hasTelegramInitDataHash(initDataRaw) && !accessToken) {
      logStartup("login request skipped", "error", {
        reason: "missing init data hash",
      });
      if (authStatus !== "error") {
        setAuthStatus("error");
      }
      return;
    }

    if (
      initDataRaw &&
      !accessToken &&
      !loginMutationRef.current.isPending &&
      (lastLoginInitDataRef.current !== initDataRaw || authStatus === "unauthenticated")
    ) {
      lastLoginInitDataRef.current = initDataRaw;
      logStartup("login request starts", authStatus, {
        hasInitDataRaw: true,
      });
      setAuthStatus("authenticating");
      loginMutationRef.current.mutate(initDataRaw, {
        onSuccess: (data) => {
          logStartup("login request succeeds", "authenticated", {
            telegramId: data.user.telegram_id,
          });
          setAccessToken(data.access_token);
          setTgUserId(data.user.telegram_id);
        },
        onError: (err) => {
          logStartup("login request fails", "error", {
            error: err instanceof Error ? err.message : String(err),
          });
          setAuthStatus("error");
        },
      });
    } else if (!initDataRaw && !accessToken && !loginMutationRef.current.isPending) {
      setAuthStatus(telegramError ? "error" : "unauthenticated");
    } else if (accessToken && authStatus !== "authenticated") {
      setAuthStatus("authenticated");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReady, initDataRaw, accessToken, tgUserId, telegramError, authStatus]);

  useEffect(() => {
    if (accessToken && initialWishlistsSettled) {
      setAppReady(true);
    } else if (!accessToken) {
      setAppReady(false);
    }
  }, [accessToken, initialWishlistsSettled, setAppReady]);

  // synchronously check if all required data is already in cache
  const isFullyCached = useMemo(() => {
    if (!wishlistsQuery.isSuccess) return false;
    const items = wishlistsQuery.data?.items ?? [];
    const hasAllWishes = items.every(wl => queryClient.getQueryData(wishQueryKeys.list(wl.id)) !== undefined);
    const hasFollowing = queryClient.getQueryData(userQueryKeys.following(tgUserId)) !== undefined;
    return hasAllWishes && hasFollowing;
  }, [wishlistsQuery.isSuccess, wishlistsQuery.data?.items, tgUserId, queryClient]);

  // Background-prefetch wish counts + following list so both tabs are instant on first visit
  useEffect(() => {
    if (!accessToken) return;

    if (wishlistsQuery.isSuccess && !initialWishesLoaded && !isFullyCached) {
      const items = wishlistsQuery.data?.items ?? [];
      // Use staleTime: Infinity so prefetchQuery resolves immediately if data is
      // already in cache (even stale). This gates the loading screen on "do we
      // have ANY data to show" rather than "is the data fresh", which prevents
      // returning users (cache > 2 min old) from seeing a long loading screen
      // while wish counts refresh. useWishesQuery has its own staleTime and will
      // background-refresh stale counts once the panel is visible.
      const wishPrefetches = items.map((wl) =>
        queryClient.prefetchQuery({
          queryKey: wishQueryKeys.list(wl.id),
          queryFn: () => listWishes(accessToken, wl.id),
          staleTime: Infinity,
        })
      );
      const followingPrefetch = queryClient.prefetchQuery({
        queryKey: userQueryKeys.following(tgUserId),
        queryFn: () => listFollowing(accessToken),
        staleTime: Infinity,
      });
      Promise.all([...wishPrefetches, followingPrefetch]).finally(() => {
        setInitialWishesLoaded(true);
      });
    } else if (wishlistsQuery.isError && !initialWishesLoaded) {
      setInitialWishesLoaded(true);
    }
  }, [accessToken, tgUserId, wishlistsQuery.data, wishlistsQuery.isSuccess, wishlistsQuery.isError, initialWishesLoaded, isFullyCached, queryClient]);

  // warm sessions initialize synchronously and do not wait for telegram sdk startup.
  // once a session exists (or is synchronously expected), hold the loading screen
  // until the wishlist list settles so the header and the panel appear together.
  // keying off accessToken alone would let the screen drop during the brief window
  // where authStatus is "authenticated" but the persisted token has not rehydrated
  // yet (or vice versa), making the panel pop in after the title.
  // also wait for the per-wishlist wish counts to be prefetched so the rows show
  // their real count instead of "..." popping in after the panel renders.
  const initialWishlistsReady = initialWishlistsSettled && (initialWishesLoaded || isFullyCached);
  const hasSession = Boolean(accessToken) || authStatus === "authenticated";
  const isLoading =
    !gateExpired &&
    (hasSession
      ? isWishlistsRoute && !initialWishlistsReady
      : !isReady || isAuthPending(authStatus));

  if (authStatus === "blocked") {
    return <BlockedScreen />;
  }

  const isMainRoute =
    isWishlistsRoute ||
    pathname === "/users" ||
    (pathname.startsWith("/users/") && pathname.split("/").length === 3);

  // Non-main routes (e.g. wishlist detail) need no shell — but still wait for
  // the loading gate to clear so we don't flash the inner page while auth is
  // still pending.
  if (!isMainRoute && !isLoading) {
    return <>{children}</>;
  }

  let title = "";
  let hideProfile = false;

  const followedUsersCount = followingQuery.data?.items?.length ?? 0;
  const bookedWishesCount = bookedWishesQuery.data?.items?.length ?? 0;
  const fulfilledWishesCount = bookedWishesQuery.data?.fulfilled_items?.length ?? 0;
  const showDiscoverTitle = followedUsersCount >= 1 || bookedWishesCount >= 1 || fulfilledWishesCount >= 1;

  if (pathname === "/wishlists" || pathname === "/") {
    title = t("wishlists");
  } else if (pathname === "/users") {
    title = showDiscoverTitle ? t("discover") : "";
  } else {
    title = t("profile");
    hideProfile = true;
  }

  const extraControls = pathname === "/users" ? <BookingVisibilityHeaderButton /> : undefined;

  // Render the full shell unconditionally so the browser pre-paints the content
  // on its own compositing layer while the loading overlay covers it.  When the
  // overlay unmounts, the already-painted content is revealed instantly — no
  // layout/paint pass, no millisecond blank frame.
  return (
    <div className="min-h-dvh flex flex-col">
      {isLoading && (
        <div className="fixed inset-0 flex items-center justify-center bg-background z-[9999]">
          <span className="auth-loading-spinner" />
        </div>
      )}
      <CoverHeader title={title} hideProfile={hideProfile} extraControls={extraControls} />
      {children}
      <BottomNav />
    </div>
  );
}

/**
 * check init data hash
 */
function hasTelegramInitDataHash(initDataRaw: string) {
  return new URLSearchParams(initDataRaw).has("hash");
}

// initialize ui settings
function UIInitializer() {
  const theme = useUIStore((state) => state.theme);
  const lang = useUIStore((state) => state.lang);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.dataset.theme = theme;
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.lang = lang;
  }, [lang]);

  return null;
}

// profile deep link token length (secrets.token_urlsafe(24) = 32 chars)
const PROFILE_TOKEN_LENGTH = 32;

type DeepLinkWindow = Window & {
  Telegram?: {
    WebApp?: {
      initDataUnsafe?: { start_param?: string };
      onEvent?: (event: string, cb: () => void) => void;
      offEvent?: (event: string, cb: () => void) => void;
    };
  };
};

function getTelegramStartParam() {
  const webAppStartParam = (window as DeepLinkWindow).Telegram?.WebApp?.initDataUnsafe?.start_param;
  const searchParams = new URLSearchParams(window.location.search);
  const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const startParam =
    webAppStartParam ||
    searchParams.get("tgWebAppStartParam") ||
    hashParams.get("tgWebAppStartParam") ||
    window.sessionStorage.getItem("wished/tgStartParam");

  if (startParam) {
    window.sessionStorage.setItem("wished/tgStartParam", startParam);
  }
  return startParam;
}

// handle startapp deep links to open profile popups
function TelegramDeepLinkHandler() {
  const router = useRouter();
  const authStatus = useAuthStore((state) => state.authStatus);
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);

  // capture the deep link destination as early as possible (before auth completes)
  useEffect(() => {
    if (typeof window === "undefined") return;

    function captureDeepLink() {
      const startParam = getTelegramStartParam();
      if (!startParam) return;

      const wishlistTarget = decodeWishlistStartParam(startParam);
      if (wishlistTarget) {
        let url =
          `/users?profile_id=${encodeURIComponent(wishlistTarget.userId)}` +
          `&wishlist=${encodeURIComponent(wishlistTarget.wishlistId)}`;
        if (wishlistTarget.shareToken) {
          url += `&share_token=${encodeURIComponent(wishlistTarget.shareToken)}`;
        }
        setPendingUrl(url);
        return;
      }

      const publicUsername = decodeProfileStartParam(startParam);
      if (publicUsername) {
        setPendingUrl(`/users?profile_public=${encodeURIComponent(publicUsername)}`);
        return;
      }

      if (startParam.length <= PROFILE_TOKEN_LENGTH) return;
      const token = startParam.slice(0, PROFILE_TOKEN_LENGTH);
      const username = startParam.slice(PROFILE_TOKEN_LENGTH);
      if (!username) return;
      setPendingUrl(`/users?profile=${encodeURIComponent(username)}&profile_token=${encodeURIComponent(token)}`);
    }

    captureDeepLink();

    const webApp = (window as DeepLinkWindow).Telegram?.WebApp;
    webApp?.onEvent?.("activated", captureDeepLink);
    return () => {
      webApp?.offEvent?.("activated", captureDeepLink);
    };
  }, []);

  // navigate only after auth is settled so Next.js does not abort the transition
  useEffect(() => {
    if (!pendingUrl || authStatus !== "authenticated") return;

    const current = new URLSearchParams(window.location.search);
    const pendingParams = new URLSearchParams(pendingUrl.split("?")[1] ?? "");
    const alreadyThere =
      current.get("profile")?.toLowerCase() === pendingParams.get("profile")?.toLowerCase() &&
      current.get("profile_public")?.toLowerCase() === pendingParams.get("profile_public")?.toLowerCase() &&
      current.get("profile_id") === pendingParams.get("profile_id") &&
      current.get("wishlist") === pendingParams.get("wishlist");
    // the deep link has now been handled — safe to drop the persisted param so it
    // doesn't re-trigger on later navigations (kept until here so a reload during
    // auth/onboarding can still recover the destination)
    window.sessionStorage.removeItem("wished/tgStartParam");
    if (alreadyThere) {
      setPendingUrl(null);
      return;
    }

    router.replace(pendingUrl);
    setPendingUrl(null);
  }, [pendingUrl, authStatus, router]);

  return null;
}

// control telegram back button
function TelegramBackButtonController() {
  const pathname = usePathname();
  const router = useRouter();
  const { isReady, initDataRaw } = useTelegram();

  useEffect(() => {
    if (!isReady || !initDataRaw) return undefined;

    try {
      if (!isBackButtonSupported()) {
        return undefined;
      }
    } catch {
      return undefined;
    }

    try {
      if (!isBackButtonMounted()) {
        mountBackButton();
      }
    } catch {
      return undefined;
    }

    const handleBack = () => {
      if (window.history.length > 1) {
        router.back();
      } else {
        router.push("/wishlists");
      }
    };
    const isMainPage = pathname === "/" || pathname === "/wishlists";

    try {
      if (isMainPage) {
        hideBackButton();
        return undefined;
      }

      showBackButton();
      onBackButtonClick(handleBack);
    } catch {
      return undefined;
    }

    return () => {
      offBackButtonClick(handleBack);
    };
  }, [initDataRaw, isReady, pathname, router]);

  return null;
}

/**
 * compose app providers
 */
export function AppProviders({ children }: AppProvidersProps) {
  const pathname = usePathname();

  return (
    <TelegramProvider>
      <QueryProvider>
        <UIInitializer />
        <TelegramDeepLinkHandler />
        <TelegramBackButtonController />
        <PersistentLayout>
          <div key={pathname} className="app-route-transition">
            {children}
          </div>
        </PersistentLayout>
      </QueryProvider>
    </TelegramProvider>
  );
}
