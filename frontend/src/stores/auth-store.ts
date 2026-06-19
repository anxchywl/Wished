"use client";

import { logStartup } from "@/lib/debug/startup-log";
import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

export type AuthStatus =
  | "bootstrap"
  | "waiting_for_telegram"
  | "telegram_ready"
  | "authenticating"
  | "authenticated"
  | "unauthenticated"
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
  clearAuth: () => void;
};

/**
 * derive initial authStatus synchronously from localStorage so warm starts
 * skip the bootstrap → waiting_for_telegram → authenticated waterfall.
 * accessToken/tgUserId still start as null and are hydrated by Zustand persist
 * — this keeps SSR and client first-render output identical (both show spinner).
 */
function getInitialAuthStatus(): AuthStatus {
  if (typeof window === "undefined") return "bootstrap";
  try {
    const raw = window.localStorage.getItem("wished-auth");
    if (!raw) return "bootstrap";
    const parsed = JSON.parse(raw) as { state?: { accessToken?: string | null } };
    return parsed?.state?.accessToken ? "authenticated" : "bootstrap";
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
