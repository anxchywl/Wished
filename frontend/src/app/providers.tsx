"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
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
import { listWishes } from "@/features/wishes/api";
import { wishQueryKeys } from "@/features/wishes/query-keys";
import { useWishlistsQuery } from "@/features/wishlists/hooks";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { CoverHeader } from "@/components/ui/cover-header";
import { BottomNav } from "@/components/ui/bottom-nav";
import { logStartup } from "@/lib/debug/startup-log";
import { isAuthPending } from "@/stores/auth-store";
import { clearPersistedCache } from "@/lib/query/cache-persister";

type AppProvidersProps = {
  children: ReactNode;
};

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
  const clearAuth = useAuthStore((state) => state.clearAuth);

  const { initDataRaw, isReady, error: telegramError } = useTelegram();
  const loginMutation = useTelegramLoginMutation();
  const wishlistsQuery = useWishlistsQuery();
  const queryClient = useQueryClient();
  const [gateExpired, setGateExpired] = useState(false);

  const loginMutationRef = useRef(loginMutation);
  loginMutationRef.current = loginMutation;

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
      if (!accessToken) setAuthStatus("waiting_for_telegram");
      return;
    }

    if (initDataRaw && authStatus === "waiting_for_telegram") {
      setAuthStatus("telegram_ready");
    }

    const currentTgUserId = getTelegramUserId(initDataRaw);

    // if account changed, clear token, query cache, and persisted cache
    if (currentTgUserId && tgUserId && currentTgUserId !== tgUserId) {
      clearPersistedCache();
      queryClient.clear();
      clearAuth();
      setTgUserId(currentTgUserId);
      setInitialWishesLoaded(false);
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
      !loginMutationRef.current.isError &&
      !loginMutationRef.current.isSuccess
    ) {
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
    if (!accessToken && loginMutation.isSuccess) {
      loginMutation.reset();
    }
  }, [accessToken, loginMutation]);

  useEffect(() => {
    if (accessToken && !wishlistsQuery.isLoading) {
      setAppReady(true);
    } else if (!accessToken) {
      setAppReady(false);
    }
  }, [accessToken, wishlistsQuery.isLoading, setAppReady]);

  const [initialWishesLoaded, setInitialWishesLoaded] = useState(false);

  // prefetch all wishlist contents silently in the background
  useEffect(() => {
    if (!accessToken) return;

    if (wishlistsQuery.isSuccess && !initialWishesLoaded) {
      if (wishlistsQuery.data?.items && wishlistsQuery.data.items.length > 0) {
        Promise.all(
          wishlistsQuery.data.items.map((wl) =>
            queryClient.prefetchQuery({
              queryKey: wishQueryKeys.list(wl.id),
              queryFn: () => listWishes(accessToken, wl.id),
            })
          )
        ).finally(() => {
          setInitialWishesLoaded(true);
        });
      } else {
        setInitialWishesLoaded(true);
      }
    } else if (wishlistsQuery.isError && !initialWishesLoaded) {
      setInitialWishesLoaded(true);
    }
  }, [accessToken, wishlistsQuery.data, wishlistsQuery.isSuccess, wishlistsQuery.isError, initialWishesLoaded, queryClient]);

  // Gate holds until auth is resolved or 10s hard timeout.
  // accessToken arrives when Zustand persist hydrates (< 1 frame after mount),
  // so warm starts lift the gate immediately without waiting for Telegram SDK.
  const isLoading =
    !gateExpired &&
    ((!isReady && !accessToken) ||
      (isAuthPending(authStatus) && !accessToken) ||
      loginMutationRef.current.isPending);

  if (isLoading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background z-[9999]">
        <span className="auth-loading-spinner" />
      </div>
    );
  }

  const isMainRoute =
    pathname === "/" ||
    pathname === "/wishlists" ||
    pathname === "/users" ||
    (pathname.startsWith("/users/") && pathname.split("/").length === 3);

  if (!isMainRoute) {
    return <>{children}</>;
  }

  let title = "";
  let hideProfile = false;

  if (pathname === "/wishlists" || pathname === "/") {
    title = t("wishlists");
  } else if (pathname === "/users") {
    title = t("discover");
  } else {
    title = t("profile");
    hideProfile = true;
  }

  return (
    <div className="min-h-dvh flex flex-col">
      <CoverHeader title={title} hideProfile={hideProfile} />
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

function getTelegramUserId(initDataRaw: string | null): number | null {
  if (!initDataRaw) {
    return null;
  }

  const user = new URLSearchParams(initDataRaw).get("user");
  if (!user) {
    return null;
  }

  try {
    const parsed = JSON.parse(user) as { id?: unknown };
    return typeof parsed.id === "number" ? parsed.id : null;
  } catch {
    return null;
  }
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

// handle startapp deep links to open profile popups
function TelegramDeepLinkHandler() {
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;

    function handleDeepLink() {
      const startParam = (window as DeepLinkWindow).Telegram?.WebApp?.initDataUnsafe?.start_param;
      if (!startParam || startParam.length <= PROFILE_TOKEN_LENGTH) return;
      const token = startParam.slice(0, PROFILE_TOKEN_LENGTH);
      const username = startParam.slice(PROFILE_TOKEN_LENGTH);
      if (!username) return;
      const current = new URLSearchParams(window.location.search);
      if (current.get("profile")?.toLowerCase() === username.toLowerCase()) return;
      router.replace(`/users?profile=${encodeURIComponent(username)}&profile_token=${encodeURIComponent(token)}`);
    }

    // SDK is loaded beforeInteractive so start_param is available immediately
    handleDeepLink();

    const webApp = (window as DeepLinkWindow).Telegram?.WebApp;
    webApp?.onEvent?.("activated", handleDeepLink);
    return () => {
      webApp?.offEvent?.("activated", handleDeepLink);
    };
  }, [router]);

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
