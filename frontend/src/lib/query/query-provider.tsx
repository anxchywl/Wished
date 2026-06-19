"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { createQueryClient } from "@/lib/query/query-client";
import { hydrateQueryClient, startPersistingQueryClient } from "@/lib/query/cache-persister";

type QueryProviderProps = {
  children: ReactNode;
};

/**
 * provide query client
 *
 * The client is hydrated from the localStorage snapshot synchronously inside
 * the lazy useState initializer — before the first render. This is what makes
 * warm starts instant: cached data is already in the cache when components
 * first read it, so no loading states flash.
 */
export function QueryProvider({ children }: QueryProviderProps) {
  const [queryClient] = useState(() => {
    const client = createQueryClient();
    hydrateQueryClient(client);
    return client;
  });

  useEffect(() => {
    return startPersistingQueryClient(queryClient);
  }, [queryClient]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
