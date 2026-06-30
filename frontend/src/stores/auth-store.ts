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
  blockReason: string | null;
  setAccessToken: (value: string | null) => void;
  setAuthStatus: (value: AuthStatus, blockReason?: string | null) => void;
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
    const parsed = JSON.parse(raw) as { state?: { accessToken?: string | null; tgUserId?: number | null; blockReason?: string | null } };
    const { accessToken, tgUserId, blockReason } = parsed?.state ?? {};

    const initDataRaw = captureTelegramInitDataFromLocation() || window.sessionStorage.getItem("wished/tgInitDataRaw");
    const currentTgUserId = initDataRaw ? extractTgUserIdFromInitData(initDataRaw) : null;

    // a different Telegram account on this device must never inherit the previous
    // user's session — including a stale "blocked" state. Detect the switch before
    // honoring blockReason so blocking one user doesn't lock out other accounts.
    if (currentTgUserId !== null && tgUserId != null && currentTgUserId !== tgUserId) {
      clearPersistedUserSession(tgUserId);
      return "bootstrap";
    }

    // blocked state only applies to the account it was set for
    if (blockReason) {
      return "blocked";
    }
    if (!accessToken) return "bootstrap";
    if (!tgUserId) {
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
      blockReason: null,
      setAccessToken: (value) =>
        set((state) => {
          // "blocked" is terminal — never let a refreshed/late token resurrect a
          // blocked session (which would render the app shell and crash)
          if (value && state.authStatus === "blocked") {
            return {};
          }
          const authStatus = value ? "authenticated" : "unauthenticated";
          logStartup("access token changed", authStatus, {
            hasAccessToken: Boolean(value),
          });
          return {
            accessToken: value,
            authStatus,
          };
        }),
      setAuthStatus: (value, blockReason) => {
        logStartup("auth status changed", value);
        set(() => {
          const next: Partial<AuthState> =
            blockReason !== undefined ? { authStatus: value, blockReason } : { authStatus: value };
          // dropping the token keeps the blocked user out of any authenticated UI
          // so only the BlockedScreen renders
          if (value === "blocked") {
            next.accessToken = null;
          }
          return next;
        });
      },
      setTgUserId: (value) => set({ tgUserId: value }),
      setAppReady: (value) => set({ isAppReady: value }),
      prepareAccountSwitch: (tgUserId) =>
        set({
          accessToken: null,
          authStatus: "telegram_ready",
          tgUserId,
          isAppReady: false,
          blockReason: null,
        }),
      clearAuth: () =>
        set({
          accessToken: null,
          authStatus: "bootstrap",
          tgUserId: null,
          isAppReady: false,
          blockReason: null,
        }),
    }),
    {
      name: "wished-auth",
      storage: createJSONStorage(() => getStorage()),
      partialize: (state) => ({ accessToken: state.accessToken, tgUserId: state.tgUserId, blockReason: state.blockReason }),
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
