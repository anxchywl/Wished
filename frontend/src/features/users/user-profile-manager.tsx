"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { PublicWishlistNavigator } from "@/features/users/public-wishlist-navigator";
import { useAuthStore } from "@/stores/auth-store";

type UserProfileManagerProps = {
  username: string;
};

/**
 * render public profile
 */
export function UserProfileManager({ username }: UserProfileManagerProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const [open, setOpen] = useState(true);
  const router = useRouter();

  function handleClose() {
    setOpen(false);
    router.push("/users");
  }

  return (
    <>
      <main className="content flex flex-col gap-4">
        {!accessToken ? (
          <AuthRequiredPanel />
        ) : null}
      </main>
      <PublicWishlistNavigator open={open} username={username} onClose={handleClose} />
    </>
  );
}
