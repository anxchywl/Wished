"use client";

import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

type AuthState = {
  accessToken: string | null;
  tgUserId: number | null;
  isAppReady: boolean;
  setAccessToken: (value: string | null) => void;
  setTgUserId: (value: number | null) => void;
  setAppReady: (value: boolean) => void;
  clearAuth: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      tgUserId: null,
      isAppReady: false,
      setAccessToken: (value) => set({ accessToken: value }),
      setTgUserId: (value) => set({ tgUserId: value }),
      setAppReady: (value) => set({ isAppReady: value }),
      clearAuth: () => set({ accessToken: null, tgUserId: null, isAppReady: false }),
    }),
    {
      name: "wished-auth",
      storage: createJSONStorage(() => getStorage()),
      partialize: (state) => ({ accessToken: state.accessToken, tgUserId: state.tgUserId }),
    },
  ),
);

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
