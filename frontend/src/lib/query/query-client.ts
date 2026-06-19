import { QueryClient } from "@tanstack/react-query";

/**
 * create query client
 *
 * Key startup-performance defaults:
 * - refetchOnWindowFocus: false — Telegram Mini App fires "focus" on every
 *   activation (switching away and back), which would trigger a refetch storm
 *   and visible flicker on every reopen. Data stays fresh via staleTime.
 * - gcTime: 24h — data must outlive the localStorage persistence window so
 *   warm-start hydration has something to restore.
 * - staleTime: 60s default — queries use cached data for 60s before a
 *   background refresh. Per-feature hooks override this where needed.
 * - refetchOnReconnect: true — refresh after network loss.
 */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
        retry: 1,
        staleTime: 60_000,
        gcTime: 24 * 60 * 60 * 1000,
      },
    },
  });
}
