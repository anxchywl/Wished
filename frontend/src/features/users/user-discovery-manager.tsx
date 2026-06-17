"use client";

import { useState } from "react";
import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { useSearchUsersQuery } from "@/features/users/hooks";
import { PublicWishlistNavigator } from "@/features/users/public-wishlist-navigator";
import { UserAvatar } from "@/features/users/user-avatar";
import type { UserSearchResponse } from "@/features/users/api";
import { normalizeTextInput } from "@/lib/forms/input-normalize";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { useAuthStore } from "@/stores/auth-store";

/**
 * discover user profiles
 */
export function UserDiscoveryManager() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedUser, setSelectedUser] = useState<UserSearchResponse | null>(null);
  const { t } = useTranslation();

  const searchResults = useSearchUsersQuery(searchQuery);

  return (
    <>
      <main className="content flex flex-col gap-4">
        {!accessToken ? (
          <AuthRequiredPanel />
        ) : (
          <div className="panel flex flex-col gap-2">
            <label className="text-sm font-semibold mb-1" htmlFor="search-user">
              {t("findProfiles")}
            </label>
            <input
              className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              id="search-user"
              onChange={(event) => setSearchQuery(normalizeTextInput(event.target.value, 100))}
              placeholder={t("enterUsernamePlaceholder")}
              value={searchQuery}
            />

            {searchQuery.trim().length > 0 && (
              <div className="flex flex-col gap-2 mt-2 border-t border-border/50 pt-2">
                {searchResults.isLoading && <p className="text-xs text-muted">{t("searching")}</p>}
                {searchResults.isLoading === false && (searchResults.data?.length ?? 0) === 0 && (
                  <p className="text-xs text-muted">{t("noUsersFound")}</p>
                )}
                <div className="flex flex-col gap-2">
                  {(searchResults.data ?? []).map((user) => (
                    <button
                      key={user.id}
                      type="button"
                      className={`flex justify-between items-center border-b border-border/50 pb-2 last:border-0 text-left ${user.username ? "" : "pointer-events-none opacity-60"}`}
                      onClick={() => setSelectedUser(user)}
                      disabled={!user.username}
                    >
                      <div className="flex items-center gap-3">
                        <UserAvatar user={user} />
                        <div>
                          <p className="text-sm font-medium">{user.first_name} {user.last_name || ""}</p>
                          {user.username ? (
                            <p className="text-xs text-primary">@{user.username}</p>
                          ) : (
                            <p className="text-xs text-muted">{t("noUsername")}</p>
                          )}
                        </div>
                      </div>
                      <span className="text-xs font-semibold text-primary">{t("viewProfile")}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      <PublicWishlistNavigator
        open={Boolean(selectedUser?.username)}
        username={selectedUser?.username ?? null}
        initialUser={selectedUser}
        onClose={() => setSelectedUser(null)}
      />
    </>
  );
}
