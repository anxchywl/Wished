"use client";

import type { LaunchParams } from "@telegram-apps/sdk-react";
import type { ReactNode } from "react";
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { init, initDataRaw as sdkInitDataRaw, mockTelegramEnv } from "@telegram-apps/sdk-react";

import { logStartup } from "@/lib/debug/startup-log";
import { captureTelegramInitDataFromLocation, getEarlyCapturedInitDataRaw, storeEarlyInitDataRaw } from "@/lib/telegram/capture-init-data";
import { useAuthStore } from "@/stores/auth-store";

type TelegramContextValue = {
  isReady: boolean;
  initDataRaw: string | null;
  error: string | null;
};

const TelegramContext = createContext<TelegramContextValue>({
  isReady: false,
  initDataRaw: null,
  error: null,
});

type TelegramProviderProps = {
  children: ReactNode;
};

type TelegramWindow = Window & {
  Telegram?: {
      WebApp?: {
      initData?: string;
      initDataUnsafe?: {
        user?: unknown;
      };
      ready?: () => void;
      expand?: () => void;
    };
  };
};

const TELEGRAM_INIT_DATA_WAIT_MS = 3_000;
const TELEGRAM_INIT_DATA_POLL_MS = 100;

/**
 * provide telegram context
 */
export function TelegramProvider({ children }: TelegramProviderProps) {
  const [isReady, setIsReady] = useState(false);
  const [initDataRaw, setInitDataRaw] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const authStatus = useAuthStore((state) => state.authStatus);
  const initialAuthStatusRef = useRef(authStatus);

  useEffect(() => {
    let cancelled = false;
    const initialAuthStatus = initialAuthStatusRef.current;
    logStartup("telegram provider mounted", initialAuthStatus, getTelegramDebugState());
    const envMock = typeof window !== "undefined" && process.env.NEXT_PUBLIC_TELEGRAM_MOCK === "1";
    const queryMock =
      typeof window !== "undefined" &&
      (window.location.search.includes("tgWebAppData=test") || window.location.hash.includes("tgWebAppData=test"));
    const shouldMock = envMock || queryMock;

    // mock telegram env
    if (shouldMock) {
      try {
        const now = new Date();
        const lp: LaunchParams = {
          platform: "web",
          version: "1.0",
          themeParams: {},
          initDataRaw: "mock_init_data",
          initData: {
            authDate: now,
            user: {
              id: 123456789,
              username: "dev",
              firstName: "Dev",
              lastName: "Developer",
              languageCode: "en",
              isPremium: false,
            },
            hash: "mockhash",
            signature: "mock-signature",
          },
        };
        mockTelegramEnv(lp);
        console.info("telegram env: mocked launch params for development");
      } catch (err) {
        console.error("mockTelegramEnv failed", err);
      }
    }

    captureTelegramInitDataFromLocation();

    const isTelegram =
      typeof window !== "undefined" &&
      (Boolean(getEarlyCapturedInitDataRaw()) ||
        window.location.search.includes("tgWebAppData") ||
        window.location.hash.includes("tgWebAppData") ||
        ("Telegram" in window));

    if (!isTelegram && !shouldMock) {
      logStartup("telegram context missing", initialAuthStatus, getTelegramDebugState());
      setError("Not running inside Telegram");
      setIsReady(true);
      return;
    }

    async function initializeTelegram() {
      let initError: unknown = null;
      if (hasTelegramLaunchParams()) {
        try {
          init();
          logStartup("telegram sdk init finished", initialAuthStatus, getTelegramDebugState());
        } catch (err) {
          initError = err;
          logStartup("telegram sdk init failed", initialAuthStatus, {
            ...getTelegramDebugState(),
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }

      const webApp = (window as TelegramWindow).Telegram?.WebApp;
      if (webApp && typeof webApp.ready === "function") {
        try {
          webApp.ready();
        } catch (err) {
          console.warn("Telegram WebApp.ready failed", err);
        }
      }
      if (webApp && typeof webApp.expand === "function") {
        try {
          webApp.expand();
        } catch (err) {
          console.warn("Telegram WebApp.expand failed", err);
        }
      }

      const rawInitData = await waitForTelegramInitDataRaw(initialAuthStatus);
      if (cancelled) return;

      setInitDataRaw(rawInitData);
      logStartup("telegram init data resolved", initialAuthStatus, {
        ...getTelegramDebugState(),
        hasResolvedInitData: Boolean(rawInitData),
      });
      if (!rawInitData && initError) {
        setError(initError instanceof Error ? initError.message : String(initError));
      }

      setIsReady(true);
    }

    void initializeTelegram();

    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(
    () => ({
      isReady,
      initDataRaw,
      error,
    }),
    [initDataRaw, isReady, error],
  );

  return <TelegramContext.Provider value={value}>{children}</TelegramContext.Provider>;
}

/**
 * use telegram context
 */
export function useTelegram() {
  return useContext(TelegramContext);
}

/**
 * get telegram init data
 */
function getTelegramInitDataRaw(): string | null {
  const earlyCaptured = getEarlyCapturedInitDataRaw();
  if (earlyCaptured) {
    return earlyCaptured;
  }

  try {
    const signalInitDataRaw = sdkInitDataRaw();
    if (signalInitDataRaw) {
      storeEarlyInitDataRaw(signalInitDataRaw);
      return signalInitDataRaw;
    }
  } catch {}

  const telegramInitData = (window as TelegramWindow).Telegram?.WebApp?.initData;
  if (telegramInitData) {
    storeEarlyInitDataRaw(telegramInitData);
  }
  return telegramInitData || null;
}

function hasTelegramLaunchParams(): boolean {
  const searchParams = new URLSearchParams(window.location.search);
  const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  return Boolean(searchParams.get("tgWebAppPlatform") || hashParams.get("tgWebAppPlatform"));
}

/**
 * get telegram debug state
 */
function getTelegramDebugState() {
  const webApp = (window as TelegramWindow).Telegram?.WebApp;
  return {
    hasTelegramObject: "Telegram" in window,
    hasWebApp: Boolean(webApp),
    hasNativeInitData: Boolean(webApp?.initData),
    hasUnsafeUser: Boolean(webApp?.initDataUnsafe?.user),
    searchHasInitData: window.location.search.includes("tgWebAppData"),
    hashHasInitData: window.location.hash.includes("tgWebAppData"),
  };
}

/**
 * wait for init data
 */
async function waitForTelegramInitDataRaw(authStatus: ReturnType<typeof useAuthStore.getState>["authStatus"]): Promise<string | null> {
  const startedAt = Date.now();
  let rawInitData = getTelegramInitDataRaw();
  let loggedWebApp = false;
  let loggedUnsafeUser = false;
  let loggedInitData = false;

  while (!rawInitData && Date.now() - startedAt < TELEGRAM_INIT_DATA_WAIT_MS) {
    const debugState = getTelegramDebugState();
    if (debugState.hasWebApp && !loggedWebApp) {
      loggedWebApp = true;
      logStartup("telegram script loaded", authStatus, debugState);
    }
    if (debugState.hasUnsafeUser && !loggedUnsafeUser) {
      loggedUnsafeUser = true;
      logStartup("telegram initDataUnsafe user exists", authStatus, debugState);
    }
    if (debugState.hasNativeInitData && !loggedInitData) {
      loggedInitData = true;
      logStartup("telegram native initData exists", authStatus, debugState);
    }
    await sleep(TELEGRAM_INIT_DATA_POLL_MS);
    rawInitData = getTelegramInitDataRaw();
  }

  return rawInitData;
}

/**
 * delay next check
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
