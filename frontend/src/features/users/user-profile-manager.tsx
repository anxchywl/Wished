"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { PublicWishlistNavigator } from "@/features/users/public-wishlist-navigator";
import { logStartup } from "@/lib/debug/startup-log";
import { isAuthFailure, isAuthPending, useAuthStore } from "@/stores/auth-store";

type UserProfileManagerProps = {
  username: string;
};

/**
 * render public profile
 */
export function UserProfileManager({ username }: UserProfileManagerProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const [open, setOpen] = useState(true);
  const router = useRouter();
  const guardDecision = isAuthPending(authStatus)
    ? "startup"
    : isAuthFailure(authStatus) || !accessToken
      ? "auth_required"
      : "app";

  logStartup("route guard decision", authStatus, {
    component: "UserProfileManager",
    decision: guardDecision,
    hasAccessToken: Boolean(accessToken),
  });

  function handleClose() {
    setOpen(false);
    router.push("/users");
  }

  return (
    <>
      <main className="content flex flex-col gap-4">
        {guardDecision === "startup" ? (
          <AuthRequiredPanel forcePending />
        ) : guardDecision === "auth_required" ? (
          <AuthRequiredPanel />
        ) : null}
      </main>
      <PublicWishlistNavigator open={open} username={username} onClose={handleClose} />
    </>
  );
}
