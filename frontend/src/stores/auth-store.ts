"use client";

import { logStartup } from "@/lib/debug/startup-log";
import { captureTelegramInitDataFromLocation, extractTgUserIdFromInitData } from "@/lib/telegram/capture-init-data";
import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

export type AuthStatus =
  | "bootstrap"
  | "waiting_for_telegram"
  | "telegram_ready"
  | "authenticating"
  | "authenticated"
  | "unauthenticated"
  | "blocked"
  | "error";

type AuthState = {
  accessToken: string | null;
  authStatus: AuthStatus;
  tgUserId: number | null;
  isAppReady: boolean;
  setAccessToken: (value: string | null) => void;
  setAuthStatus: (value: AuthStatus) => void;
  setTgUserId: (value: number | null) => void;
  setAppReady: (value: boolean) => void;
  prepareAccountSwitch: (tgUserId: number) => void;
  clearAuth: () => void;
};

/**
 * derive initial authStatus synchronously from localStorage so warm starts
 * skip the bootstrap → waiting_for_telegram → authenticated waterfall.
 *
 * when telegram init data is already available, clear a confirmed mismatched
 * session before react hydrates
 */
function getInitialAuthStatus(): AuthStatus {
  if (typeof window === "undefined") return "bootstrap";
  try {
    const raw = window.localStorage.getItem("wished-auth");
    if (!raw) return "bootstrap";
    const parsed = JSON.parse(raw) as { state?: { accessToken?: string | null; tgUserId?: number | null } };
    const { accessToken, tgUserId } = parsed?.state ?? {};
    if (!accessToken) return "bootstrap";
    if (!tgUserId) {
      clearPersistedUserSession(tgUserId);
      return "bootstrap";
    }

    const initDataRaw = captureTelegramInitDataFromLocation() || window.sessionStorage.getItem("wished/tgInitDataRaw");
    const currentTgUserId = initDataRaw ? extractTgUserIdFromInitData(initDataRaw) : null;
    if (currentTgUserId !== null && currentTgUserId !== tgUserId) {
      clearPersistedUserSession(tgUserId);
      return "bootstrap";
    }

    return "authenticated";
  } catch {
    return "bootstrap";
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      authStatus: getInitialAuthStatus(),
      tgUserId: null,
      isAppReady: false,
      setAccessToken: (value) =>
        set(() => {
          const authStatus = value ? "authenticated" : "unauthenticated";
          logStartup("access token changed", authStatus, {
            hasAccessToken: Boolean(value),
          });
          return {
            accessToken: value,
            authStatus,
          };
        }),
      setAuthStatus: (value) => {
        logStartup("auth status changed", value);
        set({ authStatus: value });
      },
      setTgUserId: (value) => set({ tgUserId: value }),
      setAppReady: (value) => set({ isAppReady: value }),
      prepareAccountSwitch: (tgUserId) =>
        set({
          accessToken: null,
          authStatus: "telegram_ready",
          tgUserId,
          isAppReady: false,
        }),
      clearAuth: () =>
        set({
          accessToken: null,
          authStatus: "bootstrap",
          tgUserId: null,
          isAppReady: false,
        }),
    }),
    {
      name: "wished-auth",
      storage: createJSONStorage(() => getStorage()),
      partialize: (state) => ({ accessToken: state.accessToken, tgUserId: state.tgUserId }),
    },
  ),
);

/**
 * check pending auth
 */
export function isAuthPending(authStatus: AuthStatus) {
  return (
    authStatus === "bootstrap" ||
    authStatus === "waiting_for_telegram" ||
    authStatus === "telegram_ready" ||
    authStatus === "authenticating"
  );
}

/**
 * check failed auth
 */
export function isAuthFailure(authStatus: AuthStatus) {
  return authStatus === "unauthenticated" || authStatus === "error";
}

/**
 * read tgUserId synchronously from local storage before zustand hydration
 */
export function getPersistedTgUserId(): number | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem("wished-auth");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { state?: { tgUserId?: number | null } };
    return parsed?.state?.tgUserId ?? null;
  } catch {
    return null;
  }
}

/**
 * hook to get tgUserId immediately on client, skipping zustand hydration delay
 */
export function useSyncTgUserId(): number | null {
  const tgUserId = useAuthStore((state) => state.tgUserId);
  const hasHydrated = useAuthStore.persist?.hasHydrated() ?? false;

  if (tgUserId === null && typeof window !== "undefined" && !hasHydrated) {
    return getPersistedTgUserId();
  }
  return tgUserId;
}

const fallbackStorage: StateStorage = {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
};

/**
 * load browser storage
 */
function getStorage(): StateStorage {
  if (typeof window !== "undefined") {
    try {
      const testKey = "wished-storage-test";
      window.localStorage.setItem(testKey, testKey);
      window.localStorage.removeItem(testKey);
      return window.localStorage;
    } catch {
      return fallbackStorage;
    }
  }

  return fallbackStorage;
}

/**
 * clear persisted user credentials and query data
 */
function clearPersistedUserSession(tgUserId: number | null | undefined) {
  window.localStorage.removeItem("wished-auth");
  window.localStorage.removeItem("wished/query-cache/v1");
  if (tgUserId != null) {
    window.localStorage.removeItem(`wished/query-cache/v1/${tgUserId}`);
  }
}
