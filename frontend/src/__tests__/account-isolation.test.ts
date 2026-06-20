/**
 * Account isolation tests.
 *
 * These prove that switching Telegram accounts on the same device cannot
 * expose one user's data to another user.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  captureTelegramInitDataFromLocation,
  extractTgUserIdFromInitData,
} from "@/lib/telegram/capture-init-data";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeInitDataRaw(userId: number): string {
  const user = JSON.stringify({ id: userId, username: "user", first_name: "User" });
  const params = new URLSearchParams({
    user,
    auth_date: String(Math.floor(Date.now() / 1000)),
    hash: "testhash",
  });
  return params.toString();
}

function makeStoredAuth(accessToken: string, tgUserId: number): string {
  return JSON.stringify({ state: { accessToken, tgUserId } });
}

// ---------------------------------------------------------------------------
// extractTgUserIdFromInitData
// ---------------------------------------------------------------------------

describe("extractTgUserIdFromInitData", () => {
  it("extracts numeric id from valid init data", () => {
    expect(extractTgUserIdFromInitData(makeInitDataRaw(123456))).toBe(123456);
  });

  it("returns null for empty string", () => {
    expect(extractTgUserIdFromInitData("")).toBeNull();
  });

  it("returns null when user field is missing", () => {
    expect(extractTgUserIdFromInitData("auth_date=1&hash=abc")).toBeNull();
  });

  it("returns null when user field is malformed JSON", () => {
    const raw = new URLSearchParams({ user: "{bad json}", hash: "h" }).toString();
    expect(extractTgUserIdFromInitData(raw)).toBeNull();
  });

  it("returns null when id is not a number", () => {
    const raw = new URLSearchParams({
      user: JSON.stringify({ id: "not-a-number" }),
      hash: "h",
    }).toString();
    expect(extractTgUserIdFromInitData(raw)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// getInitialAuthStatus (tested via localStorage + sessionStorage stubs)
// ---------------------------------------------------------------------------

// We import the store module lazily inside each test so each test gets a
// fresh module evaluation with its own localStorage/sessionStorage state.
// vitest resets modules automatically between describe blocks when we use
// vi.resetModules(), but here we test the pure sync function by directly
// calling it after setting up storage state.

describe("getInitialAuthStatus — sync identity check", () => {
  const USER_A_ID = 111111;
  const USER_B_ID = 222222;
  const ACCESS_TOKEN = "tok_test";

  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.resetModules();
  });

  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  async function callGetInitialAuthStatus(): Promise<string> {
    // Re-import to get a fresh evaluation (module state is reset by vi.resetModules())
    const mod = await import("@/stores/auth-store");
    // The function runs synchronously during module evaluation.
    // We inspect the initial state of the store which reflects the result.
    return mod.useAuthStore.getState().authStatus;
  }

  it("returns 'authenticated' for same user warm start (same user in sessionStorage)", async () => {
    window.localStorage.setItem("wished-auth", makeStoredAuth(ACCESS_TOKEN, USER_A_ID));
    window.sessionStorage.setItem("wished/tgInitDataRaw", makeInitDataRaw(USER_A_ID));

    const status = await callGetInitialAuthStatus();
    expect(status).toBe("authenticated");
  });

  it("completes persisted auth hydration without rewriting credentials", async () => {
    window.localStorage.setItem("wished-auth", makeStoredAuth(ACCESS_TOKEN, USER_A_ID));
    window.sessionStorage.setItem("wished/tgInitDataRaw", makeInitDataRaw(USER_A_ID));

    const { useAuthStore } = await import("@/stores/auth-store");
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(useAuthStore.persist.hasHydrated()).toBe(true);
    expect(useAuthStore.getState().accessToken).toBe(ACCESS_TOKEN);
    expect(useAuthStore.getState().tgUserId).toBe(USER_A_ID);
  });

  it("returns 'bootstrap' and wipes localStorage when a different user is in sessionStorage", async () => {
    window.localStorage.setItem("wished-auth", makeStoredAuth(ACCESS_TOKEN, USER_A_ID));
    window.localStorage.setItem(`wished/query-cache/v1/${USER_A_ID}`, "user-a-cache");
    window.sessionStorage.setItem("wished/tgInitDataRaw", makeInitDataRaw(USER_B_ID));

    const status = await callGetInitialAuthStatus();

    expect(status).toBe("bootstrap");
    // Stale credentials must be wiped before React renders
    expect(window.localStorage.getItem("wished-auth")).toBeNull();
    expect(window.localStorage.getItem(`wished/query-cache/v1/${USER_A_ID}`)).toBeNull();
  });

  it("keeps a warm session while Telegram identity is still loading", async () => {
    window.localStorage.setItem("wished-auth", makeStoredAuth(ACCESS_TOKEN, USER_A_ID));

    const status = await callGetInitialAuthStatus();
    expect(status).toBe("authenticated");
    expect(window.localStorage.getItem("wished-auth")).not.toBeNull();
  });

  it("returns 'bootstrap' when no accessToken is stored", async () => {
    // No entry in localStorage

    const status = await callGetInitialAuthStatus();
    expect(status).toBe("bootstrap");
  });

  it("returns 'bootstrap' when accessToken is stored but tgUserId is missing", async () => {
    window.localStorage.setItem("wished-auth", JSON.stringify({ state: { accessToken: ACCESS_TOKEN } }));

    const status = await callGetInitialAuthStatus();
    expect(status).toBe("bootstrap");
    expect(window.localStorage.getItem("wished-auth")).toBeNull();
  });

  it("does NOT wipe localStorage when users match", async () => {
    window.localStorage.setItem("wished-auth", makeStoredAuth(ACCESS_TOKEN, USER_A_ID));
    window.localStorage.setItem(`wished/query-cache/v1/${USER_A_ID}`, "user-a-cache");
    window.sessionStorage.setItem("wished/tgInitDataRaw", makeInitDataRaw(USER_A_ID));

    await callGetInitialAuthStatus();

    expect(window.localStorage.getItem("wished-auth")).not.toBeNull();
    expect(window.localStorage.getItem(`wished/query-cache/v1/${USER_A_ID}`)).toBe("user-a-cache");
  });
});

// ---------------------------------------------------------------------------
// Cache key scoping
// ---------------------------------------------------------------------------

describe("cache-persister — user-scoped cache keys", () => {
  const USER_A_ID = 111111;
  const USER_B_ID = 222222;

  beforeEach(() => {
    window.localStorage.clear();
    vi.resetModules();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("getCacheKey returns user-scoped key when tgUserId is set", async () => {
    // Pre-populate auth store with user A's persisted state
    window.localStorage.setItem(
      "wished-auth",
      JSON.stringify({ state: { accessToken: "tok", tgUserId: USER_A_ID } }),
    );
    window.sessionStorage.setItem("wished/tgInitDataRaw", makeInitDataRaw(USER_A_ID));

    const { useAuthStore } = await import("@/stores/auth-store");
    // Allow Zustand persist to hydrate
    await new Promise((r) => setTimeout(r, 0));
    expect(useAuthStore.getState().tgUserId).toBe(USER_A_ID);

    const { readPersistedSnapshot } = await import("@/lib/query/cache-persister");

    // Write a fake snapshot under user A's key
    window.localStorage.setItem(
      `wished/query-cache/v1/${USER_A_ID}`,
      JSON.stringify({ timestamp: Date.now(), buster: "2", clientState: {} }),
    );
    // Write a fake snapshot under user B's key (should never be read for user A)
    window.localStorage.setItem(
      `wished/query-cache/v1/${USER_B_ID}`,
      JSON.stringify({ timestamp: Date.now(), buster: "2", clientState: { queries: [{ key: ["user-b-data"] }] } }),
    );

    const snapshot = readPersistedSnapshot();
    // Must read user A's cache (which has an empty clientState), not user B's
    // (which has a queries array with user-b-data)
    expect(snapshot).not.toBeNull();
    const snapshotStr = JSON.stringify(snapshot);
    expect(snapshotStr).not.toContain("user-b-data");
  });

  it("getCacheKey returns bare prefix when tgUserId is null", async () => {
    // No stored auth — tgUserId is null
    const { useAuthStore } = await import("@/stores/auth-store");
    await new Promise((r) => setTimeout(r, 0));
    expect(useAuthStore.getState().tgUserId).toBeNull();

    const { readPersistedSnapshot } = await import("@/lib/query/cache-persister");

    // Nothing stored under the bare prefix
    const snapshot = readPersistedSnapshot();
    expect(snapshot).toBeNull();
  });

  it("hydrateQueryClient never migrates a shared cache into a user-scoped session", async () => {
    window.localStorage.setItem(
      "wished-auth",
      JSON.stringify({ state: { accessToken: "tok", tgUserId: USER_A_ID } }),
    );
    window.sessionStorage.setItem("wished/tgInitDataRaw", makeInitDataRaw(USER_A_ID));
    window.localStorage.setItem(
      "wished/query-cache/v1",
      JSON.stringify({ timestamp: Date.now(), buster: "2", clientState: { queries: [] } }),
    );

    const { useAuthStore } = await import("@/stores/auth-store");
    await new Promise((r) => setTimeout(r, 0)); // let Zustand persist hydrate
    expect(useAuthStore.getState().tgUserId).toBe(USER_A_ID);

    const { createQueryClient } = await import("@/lib/query/query-client");
    const { hydrateQueryClient } = await import("@/lib/query/cache-persister");

    const client = createQueryClient();
    const hydrated = hydrateQueryClient(client);

    expect(hydrated).toBe(false);
    expect(window.localStorage.getItem("wished/query-cache/v1")).toBeNull();
  });

  it("clearPersistedCache removes the current user's scoped key", async () => {
    window.localStorage.setItem(
      "wished-auth",
      JSON.stringify({ state: { accessToken: "tok", tgUserId: USER_A_ID } }),
    );
    window.sessionStorage.setItem("wished/tgInitDataRaw", makeInitDataRaw(USER_A_ID));
    const { useAuthStore } = await import("@/stores/auth-store");
    await new Promise((r) => setTimeout(r, 0));
    expect(useAuthStore.getState().tgUserId).toBe(USER_A_ID);

    window.localStorage.setItem(
      `wished/query-cache/v1/${USER_A_ID}`,
      JSON.stringify({ timestamp: Date.now(), buster: "2", clientState: {} }),
    );
    window.localStorage.setItem(
      `wished/query-cache/v1/${USER_B_ID}`,
      JSON.stringify({ timestamp: Date.now(), buster: "2", clientState: {} }),
    );

    const { clearPersistedCache } = await import("@/lib/query/cache-persister");
    clearPersistedCache();

    // User A's cache cleared; user B's cache untouched
    expect(window.localStorage.getItem(`wished/query-cache/v1/${USER_A_ID}`)).toBeNull();
    expect(window.localStorage.getItem(`wished/query-cache/v1/${USER_B_ID}`)).not.toBeNull();
  });
});

describe("Telegram init data capture", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    delete (window as Window & { Telegram?: unknown }).Telegram;
  });

  it("replaces stale session initData with the current native Telegram account", () => {
    window.sessionStorage.setItem("wished/tgInitDataRaw", makeInitDataRaw(111111));
    (window as Window & {
      Telegram?: { WebApp?: { initData?: string } };
    }).Telegram = {
      WebApp: { initData: makeInitDataRaw(222222) },
    };

    const captured = captureTelegramInitDataFromLocation();

    expect(extractTgUserIdFromInitData(captured ?? "")).toBe(222222);
    expect(
      extractTgUserIdFromInitData(window.sessionStorage.getItem("wished/tgInitDataRaw") ?? ""),
    ).toBe(222222);
  });
});
