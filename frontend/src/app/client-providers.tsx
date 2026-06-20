"use client";

import dynamic from "next/dynamic";

export const ClientAppProviders = dynamic(
  () => import("@/app/providers").then((m) => m.AppProviders),
  {
    ssr: false,
    loading: () => (
      <div className="fixed inset-0 flex items-center justify-center bg-background z-[9999]" aria-busy="true">
        <span className="auth-loading-spinner" />
      </div>
    ),
  },
);
