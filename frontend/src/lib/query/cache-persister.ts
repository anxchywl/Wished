"use client";

import type { QueryClient } from "@tanstack/react-query";
import { dehydrate, hydrate } from "@tanstack/react-query";

// Bump CACHE_BUSTER to invalidate persisted snapshots after breaking changes.
const STORAGE_KEY = "wished/query-cache/v1";
const CACHE_BUSTER = "1";
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

export function readPersistedSnapshot(): PersistedSnapshot | null {
  const storage = getStorage();
  if (!storage) return null;
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedSnapshot;
    if (parsed.buster !== CACHE_BUSTER) return null;
    if (Date.now() - parsed.timestamp > MAX_AGE_MS) {
      storage.removeItem(STORAGE_KEY);
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
  const snapshot = readPersistedSnapshot();
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
      storage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
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
    storage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
