"use client";

import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { PublicWishlistNavigator } from "@/features/users/public-wishlist-navigator";
import { UserAvatar } from "@/features/users/user-avatar";
import { useFollowingQuery } from "@/features/users/hooks";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { logStartup } from "@/lib/debug/startup-log";
import { isAuthFailure, isAuthPending, useAuthStore } from "@/stores/auth-store";
import { useRouter, useSearchParams } from "next/navigation";

type TelegramWindow = Window & {
  Telegram?: {
    WebApp?: {
      close?: () => void;
      openTelegramLink?: (url: string) => void;
    };
  };
};

/**
 * discover telegram contacts
 */
export function UserDiscoveryManager() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedUsername = searchParams.get("profile");
  const profileToken = searchParams.get("profile_token");
  const followingQuery = useFollowingQuery();
  const followedUsers = followingQuery.data?.items ?? [];
  const { t } = useTranslation();

  const guardDecision = isAuthPending(authStatus)
    ? "startup"
    : isAuthFailure(authStatus) || !accessToken
      ? "auth_required"
      : "app";

  logStartup("route guard decision", authStatus, {
    component: "UserDiscoveryManager",
    decision: guardDecision,
    hasAccessToken: Boolean(accessToken),
  });

  return (
    <>
      <main className="content discover-content">
        {guardDecision === "startup" ? (
          <AuthRequiredPanel forcePending />
        ) : guardDecision === "auth_required" ? (
          <AuthRequiredPanel />
        ) : followingQuery.isLoading ? (
          <div className="panel flex flex-col gap-3 p-4 w-full">
            <div className="public-skeleton h-16 w-full rounded-xl" />
            <div className="public-skeleton h-16 w-full rounded-xl" />
            <div className="public-skeleton h-16 w-full rounded-xl" />
          </div>
        ) : followedUsers.length > 0 ? (
          <div className="panel discover-following-panel flex flex-col p-0 overflow-hidden bg-background w-full self-start">
            <div className="discover-following">
              {followedUsers.map((user) => (
                <button
                  key={user.username}
                  type="button"
                  className="discover-following-row pressable-action"
                  onClick={() => {
                    if (user.username) router.replace(`/users?profile=${encodeURIComponent(user.username)}`);
                  }}
                  disabled={!user.username}
                >
                  <UserAvatar user={user} />
                  <span>{user.first_name || user.username}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              className="pressable-action flex items-center justify-center gap-2 py-3 px-4 w-full text-primary font-semibold text-sm cursor-pointer border-t border-border"
              onClick={openTelegramFriendPicker}
            >
              <svg className="w-4 h-4 stroke-[2.5]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              <span>{t("followNew")}</span>
            </button>
          </div>
        ) : (
          <section className="discover-launch">
            <h2>{t("findTelegramFriends")}</h2>
            <button type="button" className="discover-launch-button" onClick={openTelegramFriendPicker}>
              <span>{t("chooseTelegramUsers")}</span>
            </button>
          </section>
        )}
      </main>

      <PublicWishlistNavigator
        open={Boolean(selectedUsername)}
        username={selectedUsername}
        profileToken={profileToken}
        onClose={() => router.replace("/users")}
      />
    </>
  );
}

/**
 * open bot contact picker
 */
function openTelegramFriendPicker() {
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME?.trim().replace(/^@/, "");
  if (!botUsername) return;

  const botUrl = `https://t.me/${botUsername}`;
  const webApp = (window as TelegramWindow).Telegram?.WebApp;

  try {
    (webApp as { HapticFeedback?: { impactOccurred?: (style: string) => void } })?.HapticFeedback?.impactOccurred?.("medium");
  } catch {}

  if (webApp?.openTelegramLink) {
    webApp.openTelegramLink(botUrl);
    window.setTimeout(() => webApp.close?.(), 450);
    return;
  }

  window.location.assign(botUrl);
}
