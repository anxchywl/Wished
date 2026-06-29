"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { UIControls } from "@/components/ui/controls";
import { BirthdayPicker } from "@/components/ui/birthday-picker";
import { useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";
import { useProfileQuery, useUpdateBirthdayMutation } from "@/features/profile";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { useAdminStatus } from "@/features/admin/hooks";

/** read current user's Telegram profile photo URL directly from the WebApp SDK */
function getTelegramPhotoUrl(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const user = (window as unknown as {
      Telegram?: { WebApp?: { initDataUnsafe?: { user?: { photo_url?: string } } } };
    }).Telegram?.WebApp?.initDataUnsafe?.user;
    return user?.photo_url ?? null;
  } catch {
    return null;
  }
}

type CoverHeaderProps = {
  title: string;
  hideProfile?: boolean;
  extraControls?: React.ReactNode;
};

/**
 * gradient cover header with user profile row
 */
export function CoverHeader({ title, hideProfile = false, extraControls }: CoverHeaderProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const coverStyle = useUIStore((state) => state.coverStyle);
  const { data: profile } = useProfileQuery(accessToken);
  const updateBirthday = useUpdateBirthdayMutation();
  const { data: adminMe } = useAdminStatus();
  const isAdmin = adminMe?.is_admin === true;
  const [pickerOpen, setPickerOpen] = useState(false);
  const telegramPhotoUrl = getTelegramPhotoUrl();

  // derive display name
  const displayName = profile?.first_name
    ? [profile.first_name, profile.last_name].filter(Boolean).join(" ")
    : (profile?.username ? `@${profile.username}` : null);

  // derive initials for fallback avatar
  const initials = (displayName ?? "?")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  // format birthday for display
  function formatBirthday(raw: string | null | undefined) {
    if (!raw) return null;
    const [y, m, d] = raw.split("-");
    const months = t("months").split(",");
    return `${parseInt(d, 10)} ${months[parseInt(m, 10) - 1]} ${y}`;
  }

  function handleSave(date: string) {
    if (!accessToken) return;
    updateBirthday.mutate(
      { accessToken, birthday: date },
      { onSuccess: () => setPickerOpen(false) },
    );
  }

  function handleClear() {
    if (!accessToken) return;
    updateBirthday.mutate(
      { accessToken, birthday: null },
      { onSuccess: () => setPickerOpen(false) },
    );
  }

  return (
    <>
      <header
        className="cover cover-compact"
        style={{
          "--fallback-angle": `${coverStyle.angle}deg`,
          "--fallback-a": coverStyle.a,
          "--fallback-b": coverStyle.b,
          "--fallback-c": coverStyle.c,
          "--fallback-d": coverStyle.d,
        } as React.CSSProperties}
      >
        <UIControls prepend={extraControls} />

        {/* profile row */}
        {profile && !hideProfile && (
          <div className="cover-profile-row">
            {/* avatar — clickable only for admins */}
            <button
              type="button"
              className="cover-avatar"
              onClick={isAdmin ? () => router.push("/admin") : undefined}
              disabled={!isAdmin}
              aria-label={isAdmin ? "Admin panel" : undefined}
            >
              {telegramPhotoUrl ? (
                <>
                  <img
                    src={telegramPhotoUrl}
                    alt={displayName ?? ""}
                    className="cover-avatar-img"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                      (e.currentTarget.nextElementSibling as HTMLElement | null)?.style &&
                        ((e.currentTarget.nextElementSibling as HTMLElement).style.display = "flex");
                    }}
                  />
                  <span className="cover-avatar-initials" style={{ display: "none" }}>{initials}</span>
                </>
              ) : (
                <span className="cover-avatar-initials">{initials}</span>
              )}
            </button>

            {/* name + birthday */}
            <div className="cover-profile-meta">
              <p className="cover-profile-name">
                {displayName ?? profile.username ?? "—"}
              </p>
              <button
                className="cover-birthday-btn"
                type="button"
                onClick={() => setPickerOpen(true)}
                aria-label="Set birthday"
              >
                {profile.birthday ? (
                  <span className="cover-birthday-value">
                    {formatBirthday(profile.birthday)}
                  </span>
                ) : (
                  <span className="cover-birthday-add">+ {t("addBirthday")}</span>
                )}
              </button>
            </div>
          </div>
        )}

        {/* page title */}
        {title && <h1 className="cover-title">{title}</h1>}
      </header>

      <BirthdayPicker
        open={pickerOpen}
        initial={profile?.birthday}
        onClose={() => setPickerOpen(false)}
        onSave={handleSave}
        onClear={handleClear}
      />
    </>
  );
}
