"use client";

import type { QueryClient } from "@tanstack/react-query";
import { dehydrate, hydrate } from "@tanstack/react-query";

// Bump CACHE_BUSTER to invalidate persisted snapshots after breaking changes.
const STORAGE_KEY_PREFIX = "wished/query-cache/v1";
const CACHE_BUSTER = "3";
// gcTime in query-client.ts must be >= MAX_AGE_MS so restored data isn't GC'd.
const MAX_AGE_MS = 24 * 60 * 60 * 1000;
const SAVE_DEBOUNCE_MS = 1_000;

type PersistedSnapshot = {
  timestamp: number;
  buster: string;
  clientState: ReturnType<typeof dehydrate>;
};

function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

// Cache key is scoped by tgUserId so different Telegram accounts never share
// persisted query data. Reads directly from localStorage (not the Zustand store)
// so it works correctly in synchronous useState initialisers before Zustand persist
// has hydrated its async rehydration cycle.
function getCacheKey(): string {
  if (typeof window === "undefined") return STORAGE_KEY_PREFIX;
  try {
    const raw = window.localStorage.getItem("wished-auth");
    if (!raw) return STORAGE_KEY_PREFIX;
    const parsed = JSON.parse(raw) as { state?: { tgUserId?: number | null } };
    const tgUserId = parsed?.state?.tgUserId;
    return tgUserId != null ? `${STORAGE_KEY_PREFIX}/${tgUserId}` : STORAGE_KEY_PREFIX;
  } catch {
    return STORAGE_KEY_PREFIX;
  }
}

export function readPersistedSnapshot(): PersistedSnapshot | null {
  const storage = getStorage();
  if (!storage) return null;
  try {
    const cacheKey = getCacheKey();
    const raw = storage.getItem(cacheKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedSnapshot;
    if (parsed.buster !== CACHE_BUSTER) {
      storage.removeItem(cacheKey);
      return null;
    }
    if (Date.now() - parsed.timestamp > MAX_AGE_MS) {
      storage.removeItem(cacheKey);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function hasPersistedCache(): boolean {
  return readPersistedSnapshot() !== null;
}

export function hydrateQueryClient(queryClient: QueryClient): boolean {
  const storage = getStorage();
  const snapshot = readPersistedSnapshot();
  const cacheKey = getCacheKey();
  if (cacheKey !== STORAGE_KEY_PREFIX && storage?.getItem(STORAGE_KEY_PREFIX)) {
    storage.removeItem(STORAGE_KEY_PREFIX);
  }
  if (!snapshot) return false;
  try {
    hydrate(queryClient, snapshot.clientState);
    return true;
  } catch {
    return false;
  }
}

export function startPersistingQueryClient(queryClient: QueryClient): () => void {
  const storage = getStorage();
  if (!storage) return () => undefined;

  let timer: ReturnType<typeof setTimeout> | null = null;

  const save = () => {
    timer = null;
    try {
      const clientState = dehydrate(queryClient, {
        shouldDehydrateQuery: (query) =>
          query.state.status === "success" && query.state.data !== undefined,
      });
      const snapshot: PersistedSnapshot = {
        timestamp: Date.now(),
        buster: CACHE_BUSTER,
        clientState,
      };
      // getCacheKey() is called at save time so it always uses the current
      // (post-login) tgUserId, not the one from when the effect started.
      storage.setItem(getCacheKey(), JSON.stringify(snapshot));
    } catch {
      // quota / serialization failures are non-fatal
    }
  };

  const scheduleSave = () => {
    if (timer) return;
    timer = setTimeout(save, SAVE_DEBOUNCE_MS);
  };

  const unsubscribe = queryClient.getQueryCache().subscribe(scheduleSave);

  return () => {
    if (timer) clearTimeout(timer);
    unsubscribe();
  };
}

export function clearPersistedCache(): void {
  const storage = getStorage();
  if (!storage) return;
  try {
    storage.removeItem(getCacheKey());
  } catch {
    // ignore
  }
}
