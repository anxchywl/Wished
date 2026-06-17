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
  retrieveLaunchParams,
  showBackButton,
} from "@telegram-apps/sdk-react";

import { QueryProvider } from "@/lib/query/query-provider";
import { TelegramProvider, useTelegram } from "@/lib/telegram/telegram-provider";
import { useUIStore } from "@/stores/ui-store";
import { useAuthStore } from "@/stores/auth-store";

import { useTelegramLoginMutation } from "@/features/auth";
import { useProfileQuery } from "@/features/profile";
import { useWishlistsQuery } from "@/features/wishlists/hooks";
import { listWishes } from "@/features/wishes/api";
import { wishQueryKeys } from "@/features/wishes/query-keys";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { CoverHeader } from "@/components/ui/cover-header";
import { BottomNav } from "@/components/ui/bottom-nav";

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
  const setAccessToken = useAuthStore((state) => state.setAccessToken);
  const setAppReady = useAuthStore((state) => state.setAppReady);
  const tgUserId = useAuthStore((state) => state.tgUserId);
  const setTgUserId = useAuthStore((state) => state.setTgUserId);
  const clearAuth = useAuthStore((state) => state.clearAuth);

  const { initDataRaw, isReady } = useTelegram();
  const loginMutation = useTelegramLoginMutation();
  const profileQuery = useProfileQuery(accessToken);
  const wishlistsQuery = useWishlistsQuery();
  const queryClient = useQueryClient();

  const loginMutationRef = useRef(loginMutation);
  loginMutationRef.current = loginMutation;

  useEffect(() => {
    if (!isReady) return;

    let currentTgUserId: number | null = null;
    try {
      const lp = retrieveLaunchParams();
      currentTgUserId = lp.initData?.user?.id ?? null;
    } catch {}

    // if account changed, clear token and reset mutation
    if (currentTgUserId && tgUserId && currentTgUserId !== tgUserId) {
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

    if (
      initDataRaw &&
      !accessToken &&
      !loginMutationRef.current.isPending &&
      !loginMutationRef.current.isError &&
      !loginMutationRef.current.isSuccess
    ) {
      loginMutationRef.current.mutate(initDataRaw, {
        onSuccess: (data) => {
          setAccessToken(data.access_token);
        },
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReady, initDataRaw, accessToken, tgUserId]);

  useEffect(() => {
    if (!accessToken && loginMutation.isSuccess) {
      loginMutation.reset();
    }
  }, [accessToken, loginMutation]);

  useEffect(() => {
    if (accessToken && !profileQuery.isLoading && !wishlistsQuery.isLoading) {
      setAppReady(true);
    } else if (!accessToken) {
      setAppReady(false);
    }
  }, [accessToken, profileQuery.isLoading, wishlistsQuery.isLoading, setAppReady]);

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

  const isLoading =
    !isReady ||
    loginMutationRef.current.isPending ||
    (accessToken &&
      (profileQuery.isLoading ||
        wishlistsQuery.isLoading ||
        !initialWishesLoaded));

  if (isLoading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background z-[9999]">
        <span className="auth-loading-spinner" />
      </div>
    );
  }

  const isMainRoute =
    pathname === "/wishlists" ||
    pathname === "/users" ||
    (pathname.startsWith("/users/") && pathname.split("/").length === 3);

  if (!isMainRoute) {
    return <>{children}</>;
  }

  let title = "";
  let hideProfile = false;

  if (pathname === "/wishlists") {
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
