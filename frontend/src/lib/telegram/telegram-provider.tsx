"use client";

import type { ReactNode } from "react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { init, retrieveLaunchParams } from "@telegram-apps/sdk-react";

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

/**
 * provide telegram context
 */
export function TelegramProvider({ children }: TelegramProviderProps) {
  const [isReady, setIsReady] = useState(false);
  const [initDataRaw, setInitDataRaw] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const isTelegram =
      typeof window !== "undefined" &&
      (window.location.search.includes("tgWebAppData") ||
        window.location.hash.includes("tgWebAppData") ||
        Boolean("Telegram" in window));

    if (!isTelegram) {
      setError("Not running inside Telegram");
      setIsReady(true);
      return;
    }

    try {
      init();
      const launchParams = retrieveLaunchParams();
      setInitDataRaw(launchParams.initDataRaw ?? null);
    } catch (err) {
      console.error("Telegram init error:", err);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsReady(true);
    }
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
